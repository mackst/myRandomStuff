# --------------------------------------------------------------------------------
# Copyright (c) 2018 Shi Chi(Mack Stone). All rights reserved.
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
# --------------------------------------------------------------------------------

import os.path
import inspect
import datetime
import array

import maya.api.OpenMaya as om

import cffi
import numpy as np
from vulkan import *


WORKGROUP_SIZE = 16  # Workgroup size in compute shader.
enableValidationLayers = True


def maya_useNewAPI():
    """
    The presence of this function tells Maya that the plugin produces, and
    expects to be passed, objects created using the Maya Python API 2.0.
    """
    pass


class ClothNode(om.MPxNode):
    id = om.MTypeId(0x00105480)

    inMesh = None
    outMesh = None
    time = None

    deltaT = None
    mass = None
    stiffness = None
    damping = None
    restDistH = None
    restDistV = None
    restDistD = None
    sphereRadius = None
    spherePositionX = None
    spherePositionY = None
    spherePositionZ = None
    spherePosition = None
    gravityX = None
    gravityY = None
    gravityZ = None
    gravity = None
    pinnedIdx = None
    pinnedIdy = None
    pinnedId = None
    particleCount = None
    particleCountX = None
    particleCountY = None


    def __init__(self):
        om.MPxNode.__init__(self)

        # vulkan attributes
        self.__instance = None
        self.__debugReportCallback = None

        # The physical device is some device on the system that supports usage of Vulkan.
        # Often, it is simply a graphics card that supports Vulkan.
        self.__physicalDevice = None

        # Then we have the logical device VkDevice, which basically allows
        # us to interact with the physical device.
        self.__device = None

        # The pipeline specifies the pipeline that all graphics and compute commands pass though in Vulkan.
        # We will be creating a simple compute pipeline in this application.
        self.__pipeline = None
        self.__pipelineLayout = None
        self.__computeShaderModule = None

        # The command buffer is used to record commands, that will be submitted to a queue.
        # To allocate such command buffers, we use a command pool.
        self.__commandPool = None
        self.__commandBuffer = None

        # Descriptors represent resources in shaders. They allow us to use things like
        # uniform buffers, storage buffers and images in GLSL.
        # A single descriptor represents a single resource, and several descriptors are organized
        # into descriptor sets, which are basically just collections of descriptors.
        self.__descriptorPool = None
        self.__descriptorSet = None
        self.__descriptorSetLayout = None

        # The mandelbrot set will be rendered to this buffer.
        # The memory that backs the buffer is bufferMemory.
        self.__buffer = None
        self.__bufferMemory = None

        self.__outBuffer = None
        self.__outBufferMemory = None

        self.__uboBuffer = None
        self.__uboBufferMemory = None
        # self.__uboData = []

        # size of `buffer` in bytes.
        self.__bufferSize = 0
        self.__outBufferSize = 0
        self.__uboBufferSize = 0

        self.__enabledLayers = []

        # In order to execute commands on a device(GPU), the commands must be submitted
        # to a queue. The commands are stored in a command buffer, and this command buffer
        # is given to the queue.
        # There will be different kinds of queues on the device. Not all queues support
        # graphics operations, for instance. For this application, we at least want a queue
        # that supports compute operations.

        # a queue supporting compute operations.
        self.__queue = None

        # Groups of queues that have the same capabilities(for instance, they all supports graphics and computer operations),
        # are grouped into queue families.

        # When submitting a command buffer, you must specify to which queue in the family you are submitting to.
        # This variable keeps track of the index of that queue in its family.
        self.__queueFamilyIndex = -1

        # self.__shaderFile = os.path.join(os.path.dirname(__file__), 'cloth.spv')
        self.__shaderFile = os.path.join(os.path.dirname(inspect.getframeinfo(inspect.currentframe()).filename), 'cloth.spv')
        self.__nodeRemoveCallback = None

        self.__outPos = None

    def postConstructor(self):
        if not self.__nodeRemoveCallback:
            # self.__nodeRemoveCallback = om.MNodeMessage.addNodePreRemovalCallback(self.thisMObject(), self.cleanUp)
            self.__nodeRemoveCallback = om.MNodeMessage.addNodeAboutToDeleteCallback(self.thisMObject(), self.cleanUp)

        self.initalizeVulkan()
        # print('vulkan initalized............................................')

    def connectionMade(self, plug, otherPlug, asSrc):
        if plug == ClothNode.inMesh:
            # copy data to GPU memeory
            handle = otherPlug.asMDataHandle()
            inMesh = handle.asMesh()
            inMeshFn = om.MFnMesh(inMesh)

            pinned1Plug = om.MPlug(self.thisMObject(), self.pinnedIdx)
            pinned2Plug = om.MPlug(self.thisMObject(), self.pinnedIdy)

            points = inMeshFn.getPoints(om.MSpace.kWorld)
            pos = np.array(points, np.float32)
            vel = np.zeros_like(pos)
            pinned = np.zeros_like(pos)
            pinned[pinned1Plug.asInt()][0] = 1.0
            pinned[pinned2Plug.asInt()][0] = 1.0
            # print(pinned1Plug.asInt(), pinned2Plug.asInt())
            # print(pinned[pinned1Plug.asInt()], pinned[pinned2Plug.asInt()])
            dataArray = np.hstack([pos, vel, pinned])
            self.__outBufferSize = pos.nbytes
            # self.__outPos = np.zeros_like(pos)
            self.__outPos = pos

            self.reCreateComputePipeline(dataArray)
            print('cloth data updated.')

    def compute(self, plug, data):
        plugs = (ClothNode.deltaT, ClothNode.mass, ClothNode.stiffness, ClothNode.damping, ClothNode.restDistH,
                 ClothNode.restDistV, ClothNode.restDistD, ClothNode.sphereRadius, ClothNode.spherePositionX,
                 ClothNode.spherePositionY, ClothNode.spherePositionZ, ClothNode.gravityX, ClothNode.gravityY,
                 ClothNode.gravityZ, ClothNode.time, ClothNode.inMesh, ClothNode.outMesh)
        if plug in plugs:
            inMeshHandle = data.inputValue(ClothNode.inMesh)
            outputHandle = data.outputValue(ClothNode.outMesh)

            outMeshData = om.MFnMeshData()
            outMesh = outMeshData.create()
            meshFn = om.MFnMesh()
            newMesh = meshFn.copy(inMeshHandle.asMesh(), outMesh)

            self.clothCompute(outMesh)

            outputHandle.setMObject(outMesh)

            data.setClean(plug)
            # print('computed......')
        else:
            return None

    @staticmethod
    def cmdCreator():
        return ClothNode()

    @staticmethod
    def initialize():
        inMeshAttrFn = om.MFnTypedAttribute()
        ClothNode.inMesh = inMeshAttrFn.create('inMesh', 'im', om.MFnData.kMesh)
        inMeshAttrFn.storable = True
        inMeshAttrFn.keyable = False
        inMeshAttrFn.readable = True
        inMeshAttrFn.writable = True
        inMeshAttrFn.cached = False
        om.MPxNode.addAttribute(ClothNode.inMesh)

        outMeshAttrFn = om.MFnTypedAttribute()
        ClothNode.outMesh = outMeshAttrFn.create('outMesh', 'om', om.MFnData.kMesh)
        outMeshAttrFn.storable = True
        outMeshAttrFn.keyable = False
        outMeshAttrFn.readable = True
        outMeshAttrFn.writable = True
        outMeshAttrFn.cached = False
        om.MPxNode.addAttribute(ClothNode.outMesh)

        timeAttrFn = om.MFnNumericAttribute()
        ClothNode.time = timeAttrFn.create('time', 't', om.MFnNumericData.kInt)
        timeAttrFn.storable = False
        timeAttrFn.keyable = True
        timeAttrFn.readable = True
        timeAttrFn.writable = True
        timeAttrFn.cached = True
        om.MPxNode.addAttribute(ClothNode.time)

        # deltaT
        deltaTFn = om.MFnNumericAttribute()
        ClothNode.deltaT = deltaTFn.create('deltaT', 'dt', om.MFnNumericData.kFloat, 0.001)
        deltaTFn.storable = True
        deltaTFn.keyable = True
        deltaTFn.readable = True
        deltaTFn.writable = True
        deltaTFn.cached = True
        om.MPxNode.addAttribute(ClothNode.deltaT)

        # mass
        massFn = om.MFnNumericAttribute()
        ClothNode.mass = massFn.create('mass', 'ma', om.MFnNumericData.kFloat, 0.1)
        massFn.storable = True
        massFn.keyable = True
        massFn.readable = True
        massFn.writable = True
        massFn.cached = True
        om.MPxNode.addAttribute(ClothNode.mass)

        # stiffness
        stiffnessFn = om.MFnNumericAttribute()
        ClothNode.stiffness = stiffnessFn.create('stiffness', 'st', om.MFnNumericData.kFloat, 2000.0)
        stiffnessFn.storable = True
        stiffnessFn.keyable = True
        stiffnessFn.readable = True
        stiffnessFn.writable = True
        stiffnessFn.cached = True
        om.MPxNode.addAttribute(ClothNode.stiffness)

        # damping
        dampingFn = om.MFnNumericAttribute()
        ClothNode.damping = dampingFn.create('damping', 'da', om.MFnNumericData.kFloat, 0.25)
        dampingFn.storable = True
        dampingFn.keyable = True
        dampingFn.readable = True
        dampingFn.writable = True
        dampingFn.cached = True
        om.MPxNode.addAttribute(ClothNode.damping)

        # restDistH
        restDistHFn = om.MFnNumericAttribute()
        ClothNode.restDistH = restDistHFn.create('restDistH', 'rdh', om.MFnNumericData.kFloat, 0.0)
        restDistHFn.storable = True
        restDistHFn.keyable = True
        restDistHFn.readable = True
        restDistHFn.writable = True
        restDistHFn.cached = True
        om.MPxNode.addAttribute(ClothNode.restDistH)

        # restDistV
        restDistVFn = om.MFnNumericAttribute()
        ClothNode.restDistV = restDistVFn.create('restDistV', 'rdv', om.MFnNumericData.kFloat, 0.0)
        restDistVFn.storable = True
        restDistVFn.keyable = True
        restDistVFn.readable = True
        restDistVFn.writable = True
        restDistVFn.cached = True
        om.MPxNode.addAttribute(ClothNode.restDistV)

        # restDistD
        restDistDFn = om.MFnNumericAttribute()
        ClothNode.restDistD = restDistDFn.create('restDistD', 'rdd', om.MFnNumericData.kFloat, 0.0)
        restDistDFn.storable = True
        restDistDFn.keyable = True
        restDistDFn.readable = True
        restDistDFn.writable = True
        restDistDFn.cached = True
        om.MPxNode.addAttribute(ClothNode.restDistD)

        # sphereRadius
        sphereRadiusFn = om.MFnNumericAttribute()
        ClothNode.sphereRadius = sphereRadiusFn.create('sphereRadius', 'sr', om.MFnNumericData.kFloat, 0.0)
        sphereRadiusFn.storable = True
        sphereRadiusFn.keyable = True
        sphereRadiusFn.readable = True
        sphereRadiusFn.writable = True
        sphereRadiusFn.cached = True
        om.MPxNode.addAttribute(ClothNode.sphereRadius)

        # spherePositionX
        spherePositionXFn = om.MFnNumericAttribute()
        ClothNode.spherePositionX = spherePositionXFn.create('spherePositionX', 'sx', om.MFnNumericData.kFloat, 0.0)
        spherePositionXFn.storable = True
        spherePositionXFn.keyable = True
        spherePositionXFn.readable = True
        spherePositionXFn.writable = True
        spherePositionXFn.cached = True
        om.MPxNode.addAttribute(ClothNode.spherePositionX)

        # spherePositionY
        spherePositionYFn = om.MFnNumericAttribute()
        ClothNode.spherePositionY = spherePositionYFn.create('spherePositionY', 'sy', om.MFnNumericData.kFloat, 0.0)
        spherePositionYFn.storable = True
        spherePositionYFn.keyable = True
        spherePositionYFn.readable = True
        spherePositionYFn.writable = True
        spherePositionYFn.cached = True
        om.MPxNode.addAttribute(ClothNode.spherePositionY)

        # spherePositionZ
        spherePositionZFn = om.MFnNumericAttribute()
        ClothNode.spherePositionZ = spherePositionZFn.create('spherePositionZ', 'sz', om.MFnNumericData.kFloat, 0.0)
        spherePositionZFn.storable = True
        spherePositionZFn.keyable = True
        spherePositionZFn.readable = True
        spherePositionZFn.writable = True
        spherePositionZFn.cached = True
        om.MPxNode.addAttribute(ClothNode.spherePositionZ)

        # spherePosition
        spherePositionFn = om.MFnNumericAttribute()
        ClothNode.spherePosition = spherePositionFn.create('spherePosition', 'sp', ClothNode.spherePositionX,
                                                           ClothNode.spherePositionY, ClothNode.spherePositionZ)
        spherePositionFn.storable = False
        spherePositionFn.keyable = True
        spherePositionFn.readable = True
        spherePositionFn.writable = True
        # spherePositionFn.cached = False
        om.MPxNode.addAttribute(ClothNode.spherePosition)

        # gravityX
        gravityXFn = om.MFnNumericAttribute()
        ClothNode.gravityX = gravityXFn.create('gravityX', 'gx', om.MFnNumericData.kFloat, 0.0)
        gravityXFn.storable = True
        gravityXFn.keyable = True
        gravityXFn.readable = True
        gravityXFn.writable = True
        gravityXFn.cached = True
        om.MPxNode.addAttribute(ClothNode.gravityX)

        # gravityY
        gravityYFn = om.MFnNumericAttribute()
        ClothNode.gravityY = gravityYFn.create('gravityY', 'gy', om.MFnNumericData.kFloat, -9.8)
        gravityYFn.storable = True
        gravityYFn.keyable = True
        gravityYFn.readable = True
        gravityYFn.writable = True
        gravityYFn.cached = True
        om.MPxNode.addAttribute(ClothNode.gravityY)

        # gravityZ
        gravityZFn = om.MFnNumericAttribute()
        ClothNode.gravityZ = gravityZFn.create('gravityZ', 'gz', om.MFnNumericData.kFloat, 0.0)
        gravityZFn.storable = True
        gravityZFn.keyable = True
        gravityZFn.readable = True
        gravityZFn.writable = True
        gravityZFn.cached = True
        om.MPxNode.addAttribute(ClothNode.gravityZ)

        # gravity
        gravityFn = om.MFnNumericAttribute()
        ClothNode.gravity = gravityFn.create('gravity', 'g', ClothNode.gravityX,
                                             ClothNode.gravityY, ClothNode.gravityZ)
        gravityFn.storable = True
        gravityFn.keyable = True
        gravityFn.readable = True
        gravityFn.writable = True
        gravityFn.cached = True
        om.MPxNode.addAttribute(ClothNode.gravity)

        # pinnedId
        pinnedIdxFn = om.MFnNumericAttribute()
        ClothNode.pinnedIdx = pinnedIdxFn.create('pinnedIdX', 'px', om.MFnNumericData.kInt, 0)
        pinnedIdxFn.storable = True
        pinnedIdxFn.keyable = True
        pinnedIdxFn.readable = True
        pinnedIdxFn.writable = True
        pinnedIdxFn.cached = True
        om.MPxNode.addAttribute(ClothNode.pinnedIdx)

        # pinnedId
        pinnedIdyFn = om.MFnNumericAttribute()
        ClothNode.pinnedIdy = pinnedIdyFn.create('pinnedIdY', 'py', om.MFnNumericData.kInt, 0)
        pinnedIdyFn.storable = True
        pinnedIdyFn.keyable = True
        pinnedIdyFn.readable = True
        pinnedIdyFn.writable = True
        pinnedIdyFn.cached = True
        om.MPxNode.addAttribute(ClothNode.pinnedIdy)

        # pinnedId
        pinnedIdFn = om.MFnNumericAttribute()
        ClothNode.pinnedId = pinnedIdFn.create('pinnedId', 'pid', ClothNode.pinnedIdx, ClothNode.pinnedIdy)
        pinnedIdFn.storable = True
        pinnedIdFn.keyable = True
        pinnedIdFn.readable = True
        pinnedIdFn.writable = True
        pinnedIdFn.cached = True
        om.MPxNode.addAttribute(ClothNode.pinnedId)

        # particleCount
        particleCountxFn = om.MFnNumericAttribute()
        ClothNode.particleCountX = particleCountxFn.create('particleCountX', 'pcx', om.MFnNumericData.kInt, 0)
        particleCountxFn.storable = True
        particleCountxFn.keyable = True
        particleCountxFn.readable = True
        particleCountxFn.writable = True
        particleCountxFn.cached = True
        om.MPxNode.addAttribute(ClothNode.particleCountX)

        # particleCount
        particleCountyFn = om.MFnNumericAttribute()
        ClothNode.particleCountY = particleCountyFn.create('particleCountY', 'pcy', om.MFnNumericData.kInt, 0)
        particleCountyFn.storable = True
        particleCountyFn.keyable = True
        particleCountyFn.readable = True
        particleCountyFn.writable = True
        particleCountyFn.cached = True
        om.MPxNode.addAttribute(ClothNode.particleCountY)

        # pinnedId
        particleCountFn = om.MFnNumericAttribute()
        ClothNode.particleCount = particleCountFn.create('particleCount', 'pac', ClothNode.particleCountX, ClothNode.particleCountY)
        particleCountFn.storable = True
        particleCountFn.keyable = True
        particleCountFn.readable = True
        particleCountFn.writable = True
        particleCountFn.cached = True
        om.MPxNode.addAttribute(ClothNode.particleCount)

        om.MPxNode.attributeAffects(ClothNode.inMesh, ClothNode.outMesh)
        om.MPxNode.attributeAffects(ClothNode.time, ClothNode.outMesh)
        om.MPxNode.attributeAffects(ClothNode.deltaT, ClothNode.outMesh)
        om.MPxNode.attributeAffects(ClothNode.mass, ClothNode.outMesh)
        om.MPxNode.attributeAffects(ClothNode.stiffness, ClothNode.outMesh)
        om.MPxNode.attributeAffects(ClothNode.damping, ClothNode.outMesh)
        om.MPxNode.attributeAffects(ClothNode.restDistH, ClothNode.outMesh)
        om.MPxNode.attributeAffects(ClothNode.restDistV, ClothNode.outMesh)
        om.MPxNode.attributeAffects(ClothNode.restDistD, ClothNode.outMesh)
        om.MPxNode.attributeAffects(ClothNode.sphereRadius, ClothNode.outMesh)
        om.MPxNode.attributeAffects(ClothNode.spherePositionX, ClothNode.outMesh)
        om.MPxNode.attributeAffects(ClothNode.spherePositionY, ClothNode.outMesh)
        om.MPxNode.attributeAffects(ClothNode.spherePositionZ, ClothNode.outMesh)
        om.MPxNode.attributeAffects(ClothNode.gravityX, ClothNode.outMesh)
        om.MPxNode.attributeAffects(ClothNode.gravityY, ClothNode.outMesh)
        om.MPxNode.attributeAffects(ClothNode.gravityZ, ClothNode.outMesh)


    # ------------------------------------------------------------------------------------------------------------------
    # vulkan method
    # ------------------------------------------------------------------------------------------------------------------
    @staticmethod
    def debugReportCallbackFn(*args):
        print('Debug Report: {} {}'.format(args[5], args[6]))
        return 0

    def cleanUp(self, *args):
        if enableValidationLayers:
            # destroy callback.
            func = vkGetInstanceProcAddr(self.__instance, 'vkDestroyDebugReportCallbackEXT')
            if func == ffi.NULL:
                raise Exception("Could not load vkDestroyDebugReportCallbackEXT")
            if self.__debugReportCallback:
                func(self.__instance, self.__debugReportCallback, None)

        if self.__bufferMemory:
            vkFreeMemory(self.__device, self.__bufferMemory, None)
        if self.__buffer:
            vkDestroyBuffer(self.__device, self.__buffer, None)

        if self.__uboBufferMemory:
            vkFreeMemory(self.__device, self.__uboBufferMemory, None)
        if self.__uboBuffer:
            vkDestroyBuffer(self.__device, self.__uboBuffer, None)

        if self.__computeShaderModule:
            vkDestroyShaderModule(self.__device, self.__computeShaderModule, None)
        if self.__descriptorPool:
            vkDestroyDescriptorPool(self.__device, self.__descriptorPool, None)
        if self.__descriptorSetLayout:
            vkDestroyDescriptorSetLayout(self.__device, self.__descriptorSetLayout, None)
        if self.__pipelineLayout:
            vkDestroyPipelineLayout(self.__device, self.__pipelineLayout, None)
        if self.__pipeline:
            vkDestroyPipeline(self.__device, self.__pipeline, None)
        if self.__commandPool:
            vkDestroyCommandPool(self.__device, self.__commandPool, None)
        if self.__device:
            vkDestroyDevice(self.__device, None)
        if self.__instance:
            vkDestroyInstance(self.__instance, None)

    def initalizeVulkan(self):
        # Initialize vulkan
        self.createInstance()
        self.findPhysicalDevice()
        self.createDevice()

        # self.createBuffer()
        # self.createUniformBuffer()
        # self.createDescriptorSetLayout()
        # self.createDescriptorSet()
        # self.createComputePipeline()
        # self.createCommandBuffer()

        # Finally, run the recorded command buffer.
        #self.runCommandBuffer()

    def reCreateComputePipeline(self, particle=None):
        if self.__uboBuffer:
            vkDestroyBuffer(self.__device, self.__uboBuffer, None)
            vkFreeMemory(self.__device, self.__uboBufferMemory, None)
            self.__uboBuffer = None
        if self.__descriptorSetLayout:
            vkDestroyDescriptorSetLayout(self.__device, self.__descriptorSetLayout, None)
        if self.__descriptorPool:
            vkDestroyDescriptorPool(self.__device, self.__descriptorPool, None)
        if self.__pipelineLayout:
            vkDestroyPipelineLayout(self.__device, self.__pipelineLayout, None)
        if self.__pipeline:
            vkDestroyPipeline(self.__device, self.__pipeline, None)
        if self.__commandPool:
            vkDestroyCommandPool(self.__device, self.__commandPool, None)

        self.createDescriptorSetLayout()
        self.createComputePipeline()
        self.createCommandPool()

        if particle is not None:
            if self.__buffer:
                vkDestroyBuffer(self.__device, self.__buffer, None)
                vkFreeMemory(self.__device, self.__bufferMemory, None)
                vkDestroyBuffer(self.__device, self.__outBuffer, None)
                vkFreeMemory(self.__device, self.__outBufferMemory, None)

                self.__buffer = None
                self.__outBuffer = None

            self.createClothBuffer(particle)

        self.createUniformBuffer()
        self.createDescriptorSet()
        self.createCommandBuffer()

    def clothCompute(self, inMesh):
        self.updateUniformBuffer()
        self.runCommandBuffer()

        pmappedMemory = vkMapMemory(self.__device, self.__outBufferMemory, 0, self.__outBufferSize, 0)
        dataPtr = ffi.cast('float *', self.__outPos.ctypes.data)
        ffi.memmove(dataPtr, pmappedMemory, self.__outBufferSize)
        vkUnmapMemory(self.__device, self.__outBufferMemory)

        newPos = om.MPointArray(self.__outPos.tolist())
        outMeshFn = om.MFnMesh(inMesh)
        # outMeshFn.setPoints(newPos)
        outMeshFn.setPoints(newPos, om.MSpace.kWorld)

    def createInstance(self):
        enabledExtensions = []
        # By enabling validation layers, Vulkan will emit warnings if the API
        # is used incorrectly. We shall enable the layer VK_LAYER_LUNARG_standard_validation,
        # which is basically a collection of several useful validation layers.
        if enableValidationLayers:
            # We get all supported layers with vkEnumerateInstanceLayerProperties.
            layerProperties = vkEnumerateInstanceLayerProperties()

            # And then we simply check if VK_LAYER_LUNARG_standard_validation is among the supported layers.
            supportLayerNames = [prop.layerName for prop in layerProperties]
            if "VK_LAYER_LUNARG_standard_validation" not in supportLayerNames:
                raise Exception('Layer VK_LAYER_LUNARG_standard_validation not supported')
            self.__enabledLayers.append("VK_LAYER_LUNARG_standard_validation")

            # We need to enable an extension named VK_EXT_DEBUG_REPORT_EXTENSION_NAME,
            # in order to be able to print the warnings emitted by the validation layer.
            # So again, we just check if the extension is among the supported extensions.
            extensionProperties = vkEnumerateInstanceExtensionProperties(None)

            supportExtensions = [prop.extensionName for prop in extensionProperties]
            if VK_EXT_DEBUG_REPORT_EXTENSION_NAME not in supportExtensions:
                raise Exception('Extension VK_EXT_DEBUG_REPORT_EXTENSION_NAME not supported')
            enabledExtensions.append(VK_EXT_DEBUG_REPORT_EXTENSION_NAME)

        # Next, we actually create the instance.

        # Contains application info. This is actually not that important.
        # The only real important field is apiVersion.
        applicationInfo = VkApplicationInfo(
            sType=VK_STRUCTURE_TYPE_APPLICATION_INFO,
            pApplicationName='Cloth Sim',
            applicationVersion=0,
            pEngineName='clothsim',
            engineVersion=0,
            apiVersion=VK_API_VERSION_1_0
        )

        createInfo = VkInstanceCreateInfo(
            sType=VK_STRUCTURE_TYPE_INSTANCE_CREATE_INFO,
            flags=0,
            pApplicationInfo=applicationInfo,
            # Give our desired layers and extensions to vulkan.
            enabledLayerCount=len(self.__enabledLayers),
            ppEnabledLayerNames=self.__enabledLayers,
            enabledExtensionCount=len(enabledExtensions),
            ppEnabledExtensionNames=enabledExtensions
        )

        # Actually create the instance.
        # Having created the instance, we can actually start using vulkan.
        self.__instance = vkCreateInstance(createInfo, None)

        # Register a callback function for the extension VK_EXT_DEBUG_REPORT_EXTENSION_NAME, so that warnings
        # emitted from the validation layer are actually printed.
        if enableValidationLayers:
            createInfo = VkDebugReportCallbackCreateInfoEXT(
                sType=VK_STRUCTURE_TYPE_DEBUG_REPORT_CALLBACK_CREATE_INFO_EXT,
                flags=VK_DEBUG_REPORT_ERROR_BIT_EXT | VK_DEBUG_REPORT_WARNING_BIT_EXT | VK_DEBUG_REPORT_PERFORMANCE_WARNING_BIT_EXT,
                pfnCallback=self.debugReportCallbackFn
            )

            # We have to explicitly load this function.
            vkCreateDebugReportCallbackEXT = vkGetInstanceProcAddr(self.__instance, 'vkCreateDebugReportCallbackEXT')
            if vkCreateDebugReportCallbackEXT == ffi.NULL:
                raise Exception('Could not load vkCreateDebugReportCallbackEXT')

            # Create and register callback.
            self.__debugReportCallback = vkCreateDebugReportCallbackEXT(self.__instance, createInfo, None)

    def findPhysicalDevice(self):
        # In this function, we find a physical device that can be used with Vulkan.
        # So, first we will list all physical devices on the system with vkEnumeratePhysicalDevices.
        devices = vkEnumeratePhysicalDevices(self.__instance)

        # Next, we choose a device that can be used for our purposes.
        # With VkPhysicalDeviceFeatures(), we can retrieve a fine-grained list of physical features supported by the device.
        # However, in this demo, we are simply launching a simple compute shader, and there are no
        # special physical features demanded for this task.
        # With VkPhysicalDeviceProperties(), we can obtain a list of physical device properties. Most importantly,
        # we obtain a list of physical device limitations. For this application, we launch a compute shader,
        # and the maximum size of the workgroups and total number of compute shader invocations is limited by the physical device,
        # and we should ensure that the limitations named maxComputeWorkGroupCount, maxComputeWorkGroupInvocations and
        # maxComputeWorkGroupSize are not exceeded by our application.  Moreover, we are using a storage buffer in the compute shader,
        # and we should ensure that it is not larger than the device can handle, by checking the limitation maxStorageBufferRange.
        # However, in our application, the workgroup size and total number of shader invocations is relatively small, and the storage buffer is
        # not that large, and thus a vast majority of devices will be able to handle it. This can be verified by looking at some devices at_
        # http://vulkan.gpuinfo.org/
        # Therefore, to keep things simple and clean, we will not perform any such checks here, and just pick the first physical
        # device in the list. But in a real and serious application, those limitations should certainly be taken into account.

        # just use the first one
        self.__physicalDevice = devices[0]

    # Returns the index of a queue family that supports compute operations.
    def getComputeQueueFamilyIndex(self):
        # Retrieve all queue families.
        queueFamilies = vkGetPhysicalDeviceQueueFamilyProperties(self.__physicalDevice)

        # Now find a family that supports compute.
        for i, props in enumerate(queueFamilies):
            if props.queueCount > 0 and props.queueFlags & VK_QUEUE_COMPUTE_BIT:
                # found a queue with compute. We're done!
                return i

        return -1

    def createDevice(self):
        # We create the logical device in this function.

        self.__queueFamilyIndex = self.getComputeQueueFamilyIndex()
        # When creating the device, we also specify what queues it has.
        queueCreateInfo = VkDeviceQueueCreateInfo(
            sType=VK_STRUCTURE_TYPE_DEVICE_QUEUE_CREATE_INFO,
            queueFamilyIndex=self.__queueFamilyIndex,  # find queue family with compute capability.
            queueCount=1,  # create one queue in this family. We don't need more.
            pQueuePriorities=[1.0]  # we only have one queue, so this is not that imporant.
        )

        # Now we create the logical device. The logical device allows us to interact with the physical device.
        # Specify any desired device features here. We do not need any for this application, though.
        deviceFeatures = VkPhysicalDeviceFeatures()
        deviceCreateInfo = VkDeviceCreateInfo(
            sType=VK_STRUCTURE_TYPE_DEVICE_CREATE_INFO,
            enabledLayerCount=len(self.__enabledLayers),
            ppEnabledLayerNames=self.__enabledLayers,
            pQueueCreateInfos=queueCreateInfo,
            queueCreateInfoCount=1,
            pEnabledFeatures=deviceFeatures
        )

        self.__device = vkCreateDevice(self.__physicalDevice, deviceCreateInfo, None)
        self.__queue = vkGetDeviceQueue(self.__device, self.__queueFamilyIndex, 0)

    # find memory type with desired properties.
    def findMemoryType(self, memoryTypeBits, properties):
        memoryProperties = vkGetPhysicalDeviceMemoryProperties(self.__physicalDevice)

        # How does this search work?
        # See the documentation of VkPhysicalDeviceMemoryProperties for a detailed description.
        for i, mt in enumerate(memoryProperties.memoryTypes):
            if memoryTypeBits & (1 << i) and (mt.propertyFlags & properties) == properties:
                return i

        return -1

    def __createBuffer(self, size, usage, properties):
        buffer = None
        bufferMemory = None

        bufferInfo = VkBufferCreateInfo(
            size=size,
            usage=usage,
            sharingMode=VK_SHARING_MODE_EXCLUSIVE
        )

        buffer = vkCreateBuffer(self.__device, bufferInfo, None)

        memRequirements = vkGetBufferMemoryRequirements(self.__device, buffer)
        allocInfo = VkMemoryAllocateInfo(
            allocationSize=memRequirements.size,
            memoryTypeIndex=self.findMemoryType(memRequirements.memoryTypeBits, properties)
        )
        bufferMemory = vkAllocateMemory(self.__device, allocInfo, None)

        vkBindBufferMemory(self.__device, buffer, bufferMemory, 0)

        return (buffer, bufferMemory)

    def __beginSingleTimeCommands(self):
        allocInfo = VkCommandBufferAllocateInfo(
            level=VK_COMMAND_BUFFER_LEVEL_PRIMARY,
            commandPool=self.__commandPool,
            commandBufferCount=1
        )

        commandBuffer = vkAllocateCommandBuffers(self.__device, allocInfo)[0]
        beginInfo = VkCommandBufferBeginInfo(flags=VK_COMMAND_BUFFER_USAGE_ONE_TIME_SUBMIT_BIT)
        vkBeginCommandBuffer(commandBuffer, beginInfo)

        return commandBuffer

    def __endSingleTimeCommands(self, commandBuffer):
        vkEndCommandBuffer(commandBuffer)

        submitInfo = VkSubmitInfo(pCommandBuffers=[commandBuffer])

        vkQueueSubmit(self.__queue, 1, [submitInfo], VK_NULL_HANDLE)
        vkQueueWaitIdle(self.__queue)

        vkFreeCommandBuffers(self.__device, self.__commandPool, 1, [commandBuffer])

    def __copyBuffer(self, src, dst, bufferSize):
        commandBuffer = self.__beginSingleTimeCommands()

        copyRegion = VkBufferCopy(0, 0, bufferSize)
        vkCmdCopyBuffer(commandBuffer, src, dst, 1, [copyRegion])

        self.__endSingleTimeCommands(commandBuffer)

    def createClothBuffer(self, particle):
        self.__bufferSize = particle.nbytes

        stagingBuffer, stagingMem = self.__createBuffer(self.__bufferSize, VK_BUFFER_USAGE_TRANSFER_SRC_BIT,
                                                        VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT | VK_MEMORY_PROPERTY_HOST_COHERENT_BIT)

        data = vkMapMemory(self.__device, stagingMem, 0, self.__bufferSize, 0)
        dataPtr = ffi.cast('float *', particle.ctypes.data)
        ffi.memmove(data, dataPtr, self.__bufferSize)
        vkUnmapMemory(self.__device, stagingMem)

        self.__buffer, self.__bufferMemory = self.__createBuffer(self.__bufferSize, VK_BUFFER_USAGE_TRANSFER_DST_BIT | VK_BUFFER_USAGE_STORAGE_BUFFER_BIT,
                                                                 VK_MEMORY_PROPERTY_DEVICE_LOCAL_BIT)
        self.__copyBuffer(stagingBuffer, self.__buffer, self.__bufferSize)

        vkDestroyBuffer(self.__device, stagingBuffer, None)
        vkFreeMemory(self.__device, stagingMem, None)

        if self.__outBuffer is None:
            self.__outBuffer, self.__outBufferMemory = self.__createBuffer(self.__outBufferSize,
                                                                           VK_BUFFER_USAGE_STORAGE_BUFFER_BIT,
                                                                           VK_MEMORY_PROPERTY_HOST_COHERENT_BIT | VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT)
            data = vkMapMemory(self.__device, self.__outBufferMemory, 0, self.__outBufferSize, 0)
            dataPtr = ffi.cast('float *', self.__outPos.ctypes.data)
            ffi.memmove(data, dataPtr, self.__outBufferSize)
            vkUnmapMemory(self.__device, self.__outBufferMemory)

    def getUBODataArray(self):
        deltaTPlug = om.MPlug(self.thisMObject(), self.deltaT)
        deltaT = deltaTPlug.asFloat()

        massPlug = om.MPlug(self.thisMObject(), self.mass)
        mass = massPlug.asFloat()

        stiffnessPlug = om.MPlug(self.thisMObject(), self.stiffness)
        stiffness = stiffnessPlug.asFloat()

        dampingPlug = om.MPlug(self.thisMObject(), self.damping)
        damping = dampingPlug.asFloat()

        restDistHPlug = om.MPlug(self.thisMObject(), self.restDistH)
        restDisH = restDistHPlug.asFloat()

        restDistVPlug = om.MPlug(self.thisMObject(), self.restDistV)
        restDisV = restDistVPlug.asFloat()

        restDistDPlug = om.MPlug(self.thisMObject(), self.restDistD)
        restDisD = restDistDPlug.asFloat()

        sphereRadiusPlug = om.MPlug(self.thisMObject(), self.sphereRadius)
        sphereRadius = sphereRadiusPlug.asFloat()

        spherePositionXPlug = om.MPlug(self.thisMObject(), self.spherePositionX)
        spherePositionX = spherePositionXPlug.asFloat()

        spherePositionYPlug = om.MPlug(self.thisMObject(), self.spherePositionY)
        spherePositionY = spherePositionYPlug.asFloat()

        spherePositionZPlug = om.MPlug(self.thisMObject(), self.spherePositionZ)
        spherePositionZ = spherePositionZPlug.asFloat()

        gravityXPlug = om.MPlug(self.thisMObject(), self.gravityX)
        gravityX = gravityXPlug.asFloat()

        gravityYPlug = om.MPlug(self.thisMObject(), self.gravityY)
        gravityY = gravityYPlug.asFloat()

        gravityZPlug = om.MPlug(self.thisMObject(), self.gravityZ)
        gravityZ = gravityZPlug.asFloat()

        particleCountXPlug = om.MPlug(self.thisMObject(), self.particleCountX)
        pcx = particleCountXPlug.asFloat()

        particleCountYPlug = om.MPlug(self.thisMObject(), self.particleCountY)
        pcy = particleCountYPlug.asFloat()

        return array.array('f',
                           [deltaT, mass, stiffness, damping,
                            restDisH, restDisV, restDisD, sphereRadius,
                            spherePositionX, spherePositionY, spherePositionZ, 0,
                            gravityX, gravityY, gravityZ, 0,
                            pcx, pcy, 0, 0])


    def createUniformBuffer(self):
        # ubo
        uboArray = self.getUBODataArray()
        # uboArray = np.array(uboArray)
        # self.__uboBufferSize = uboArray.nbytes
        self.__uboBufferSize = uboArray.itemsize * len(uboArray)

        bufferCreateInfo = VkBufferCreateInfo(
            size=self.__uboBufferSize,  # buffer size in bytes.
            usage=VK_BUFFER_USAGE_UNIFORM_BUFFER_BIT,  # buffer is used as a storage buffer.
            sharingMode=VK_SHARING_MODE_EXCLUSIVE  # buffer is exclusive to a single queue family at a time.
        )

        self.__uboBuffer = vkCreateBuffer(self.__device, bufferCreateInfo, None)

        memoryRequirements = vkGetBufferMemoryRequirements(self.__device, self.__uboBuffer)
        index = self.findMemoryType(memoryRequirements.memoryTypeBits,
                                    VK_MEMORY_PROPERTY_HOST_COHERENT_BIT | VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT)
        allocateInfo = VkMemoryAllocateInfo(
            allocationSize=memoryRequirements.size,  # specify required memory.
            memoryTypeIndex=index
        )

        self.__uboBufferMemory = vkAllocateMemory(self.__device, allocateInfo, None)

        data = vkMapMemory(self.__device, self.__uboBufferMemory, 0, self.__uboBufferSize, 0)
        # dptr = ffi.cast('float *', uboArray.ctypes.data)
        dptr = ffi.cast('float *', uboArray.buffer_info()[0])
        ffi.memmove(data, dptr, self.__uboBufferSize)
        vkUnmapMemory(self.__device, self.__uboBufferMemory)

        vkBindBufferMemory(self.__device, self.__uboBuffer, self.__uboBufferMemory, 0)

    def updateUniformBuffer(self):
        uboArray = self.getUBODataArray()
        # uboArray = np.array(uboArray)
        # print(uboArray)
        data = vkMapMemory(self.__device, self.__uboBufferMemory, 0, self.__uboBufferSize, 0)
        # dptr = ffi.cast('float *', uboArray.ctypes.data)
        dptr = ffi.cast('float *', uboArray.buffer_info()[0])
        ffi.memmove(data, dptr, self.__uboBufferSize)
        vkUnmapMemory(self.__device, self.__uboBufferMemory)

    def createDescriptorSetLayout(self):
        # Here we specify a descriptor set layout. This allows us to bind our descriptors to
        # resources in the shader.

        # Here we specify a binding of type VK_DESCRIPTOR_TYPE_STORAGE_BUFFER to the binding point
        # 0. This binds to
        #   layout(std140, binding = 0) buffer buf
        # in the compute shader.
        descriptorSetLayoutBindings = [
            # in data
            VkDescriptorSetLayoutBinding(
                binding=0,
                descriptorType=VK_DESCRIPTOR_TYPE_STORAGE_BUFFER,
                descriptorCount=1,
                stageFlags=VK_SHADER_STAGE_COMPUTE_BIT
            ),
            # out position
            VkDescriptorSetLayoutBinding(
                binding=1,
                descriptorType=VK_DESCRIPTOR_TYPE_STORAGE_BUFFER,
                descriptorCount=1,
                stageFlags=VK_SHADER_STAGE_COMPUTE_BIT
            ),
            # UBO
            VkDescriptorSetLayoutBinding(
                binding=2,
                descriptorType=VK_DESCRIPTOR_TYPE_UNIFORM_BUFFER,
                descriptorCount=1,
                stageFlags=VK_SHADER_STAGE_COMPUTE_BIT
            ),
        ]

        descriptorSetLayoutCreateInfo = VkDescriptorSetLayoutCreateInfo(
            # bindingCount=1,  # only a single binding in this descriptor set layout.
            pBindings=descriptorSetLayoutBindings
        )

        # Create the descriptor set layout.
        self.__descriptorSetLayout = vkCreateDescriptorSetLayout(self.__device, descriptorSetLayoutCreateInfo, None)

    def createDescriptorSet(self):
        # So we will allocate a descriptor set here.
        # But we need to first create a descriptor pool to do that.

        # Our descriptor pool can only allocate a single storage buffer.

        descriptorPoolSizes = [
            VkDescriptorPoolSize(
                type=VK_DESCRIPTOR_TYPE_STORAGE_BUFFER,
                descriptorCount=2
            ),
            VkDescriptorPoolSize(
                type=VK_DESCRIPTOR_TYPE_UNIFORM_BUFFER,
                descriptorCount=1
            )
        ]

        descriptorPoolCreateInfo = VkDescriptorPoolCreateInfo(
            maxSets=1,  # we only need to allocate one descriptor set from the pool.
            # poolSizeCount=1,
            pPoolSizes=descriptorPoolSizes
        )

        # create descriptor pool.
        self.__descriptorPool = vkCreateDescriptorPool(self.__device, descriptorPoolCreateInfo, None)

        # With the pool allocated, we can now allocate the descriptor set.
        descriptorSetAllocateInfo = VkDescriptorSetAllocateInfo(
            sType=VK_STRUCTURE_TYPE_DESCRIPTOR_SET_ALLOCATE_INFO,
            descriptorPool=self.__descriptorPool,
            descriptorSetCount=1,
            pSetLayouts=[self.__descriptorSetLayout]
        )

        # allocate descriptor set.
        self.__descriptorSet = vkAllocateDescriptorSets(self.__device, descriptorSetAllocateInfo)[0]

        # Next, we need to connect our actual storage buffer with the descrptor.
        # We use vkUpdateDescriptorSets() to update the descriptor set.

        # Specify the buffer to bind to the descriptor.
        descriptorBufferInfo = VkDescriptorBufferInfo(
            buffer=self.__buffer,
            offset=0,
            range=self.__bufferSize
        )

        uboBufferInfo = VkDescriptorBufferInfo(
            buffer=self.__uboBuffer,
            offset=0,
            range=self.__uboBufferSize
        )

        outBufferInfo = VkDescriptorBufferInfo(
            buffer=self.__outBuffer,
            offset=0,
            range=self.__outBufferSize
        )

        writeDescriptorSets = [
            VkWriteDescriptorSet(
                dstSet=self.__descriptorSet,
                dstBinding=0,  # write to the first, and only binding.
                descriptorCount=1,
                descriptorType=VK_DESCRIPTOR_TYPE_STORAGE_BUFFER,
                pBufferInfo=descriptorBufferInfo
            ),

            VkWriteDescriptorSet(
                dstSet=self.__descriptorSet,
                dstBinding=1,  # write to the first, and only binding.
                descriptorCount=1,
                descriptorType=VK_DESCRIPTOR_TYPE_STORAGE_BUFFER,
                pBufferInfo=outBufferInfo
            ),

            VkWriteDescriptorSet(
                dstSet=self.__descriptorSet,
                dstBinding=2,  # write to the first, and only binding.
                descriptorCount=1,
                descriptorType=VK_DESCRIPTOR_TYPE_UNIFORM_BUFFER,
                pBufferInfo=uboBufferInfo
            ),
        ]

        # perform the update of the descriptor set.
        vkUpdateDescriptorSets(self.__device, len(writeDescriptorSets), writeDescriptorSets, 0, None)

    def createComputePipeline(self):
        # We create a compute pipeline here.

        # Create a shader module. A shader module basically just encapsulates some shader code.
        with open(self.__shaderFile, 'rb') as comp:
            code = comp.read()

            createInfo = VkShaderModuleCreateInfo(
                sType=VK_STRUCTURE_TYPE_SHADER_MODULE_CREATE_INFO,
                codeSize=len(code),
                pCode=code
            )

            self.__computeShaderModule = vkCreateShaderModule(self.__device, createInfo, None)

        # Now let us actually create the compute pipeline.
        # A compute pipeline is very simple compared to a graphics pipeline.
        # It only consists of a single stage with a compute shader.
        # So first we specify the compute shader stage, and it's entry point(main).
        shaderStageCreateInfo = VkPipelineShaderStageCreateInfo(
            sType=VK_STRUCTURE_TYPE_PIPELINE_SHADER_STAGE_CREATE_INFO,
            stage=VK_SHADER_STAGE_COMPUTE_BIT,
            module=self.__computeShaderModule,
            pName='main'
        )

        # The pipeline layout allows the pipeline to access descriptor sets.
        # So we just specify the descriptor set layout we created earlier.
        pipelineLayoutCreateInfo = VkPipelineLayoutCreateInfo(
            sType=VK_STRUCTURE_TYPE_PIPELINE_LAYOUT_CREATE_INFO,
            setLayoutCount=1,
            pSetLayouts=[self.__descriptorSetLayout]
        )
        self.__pipelineLayout = vkCreatePipelineLayout(self.__device, pipelineLayoutCreateInfo, None)

        pipelineCreateInfo = VkComputePipelineCreateInfo(
            sType=VK_STRUCTURE_TYPE_COMPUTE_PIPELINE_CREATE_INFO,
            stage=shaderStageCreateInfo,
            layout=self.__pipelineLayout
        )

        # Now, we finally create the compute pipeline.
        self.__pipeline = vkCreateComputePipelines(self.__device, VK_NULL_HANDLE, 1, pipelineCreateInfo, None)

    def createCommandPool(self):
        commandPoolCreateInfo = VkCommandPoolCreateInfo(
            # the queue family of this command pool. All command buffers allocated from this command pool,
            # must be submitted to queues of this family ONLY.
            queueFamilyIndex=self.__queueFamilyIndex
        )

        self.__commandPool = vkCreateCommandPool(self.__device, commandPoolCreateInfo, None)

    def createCommandBuffer(self):
        # We are getting closer to the end. In order to send commands to the device(GPU),
        # we must first record commands into a command buffer.

        # Now allocate a command buffer from the command pool.
        commandBufferAllocateInfo = VkCommandBufferAllocateInfo(
            sType=VK_STRUCTURE_TYPE_COMMAND_BUFFER_ALLOCATE_INFO,
            commandPool=self.__commandPool,
            # if the command buffer is primary, it can be directly submitted to queues.
            # A secondary buffer has to be called from some primary command buffer, and cannot be directly
            # submitted to a queue. To keep things simple, we use a primary command buffer.
            level=VK_COMMAND_BUFFER_LEVEL_PRIMARY,
            commandBufferCount=1
        )

        self.__commandBuffer = vkAllocateCommandBuffers(self.__device, commandBufferAllocateInfo)[0]

        # Now we shall start recording commands into the newly allocated command buffer.
        beginInfo = VkCommandBufferBeginInfo(
            sType=VK_STRUCTURE_TYPE_COMMAND_BUFFER_BEGIN_INFO,
            # the buffer is only submitted and used once in this application.
            flags=VK_COMMAND_BUFFER_USAGE_ONE_TIME_SUBMIT_BIT
        )
        vkBeginCommandBuffer(self.__commandBuffer, beginInfo)

        # We need to bind a pipeline, AND a descriptor set before we dispatch.
        # The validation layer will NOT give warnings if you forget these, so be very careful not to forget them.
        vkCmdBindPipeline(self.__commandBuffer, VK_PIPELINE_BIND_POINT_COMPUTE, self.__pipeline)
        vkCmdBindDescriptorSets(self.__commandBuffer, VK_PIPELINE_BIND_POINT_COMPUTE, self.__pipelineLayout,
                                0, 1, [self.__descriptorSet], 0, None)

        # Calling vkCmdDispatch basically starts the compute pipeline, and executes the compute shader.
        # The number of workgroups is specified in the arguments.
        # If you are already familiar with compute shaders from OpenGL, this should be nothing new to you.
        vkCmdDispatch(self.__commandBuffer,
                      WORKGROUP_SIZE,
                      WORKGROUP_SIZE,
                      1)

        vkEndCommandBuffer(self.__commandBuffer)

    def runCommandBuffer(self):
        # Now we shall finally submit the recorded command buffer to a queue.
        submitInfo = VkSubmitInfo(
            sType=VK_STRUCTURE_TYPE_SUBMIT_INFO,
            commandBufferCount=1,  # submit a single command buffer
            pCommandBuffers=[self.__commandBuffer]  # the command buffer to submit.
        )

        # We create a fence.
        fenceCreateInfo = VkFenceCreateInfo(
            sType=VK_STRUCTURE_TYPE_FENCE_CREATE_INFO,
            flags=0
        )
        fence = vkCreateFence(self.__device, fenceCreateInfo, None)

        # We submit the command buffer on the queue, at the same time giving a fence.
        vkQueueSubmit(self.__queue, 1, submitInfo, fence)

        # The command will not have finished executing until the fence is signalled.
        # So we wait here.
        # We will directly after this read our buffer from the GPU,
        # and we will not be sure that the command has finished executing unless we wait for the fence.
        # Hence, we use a fence here.
        vkWaitForFences(self.__device, 1, [fence], VK_TRUE, 100000000000)

        vkDestroyFence(self.__device, fence, None)


# INITIALIZES THE PLUGIN BY REGISTERING THE COMMAND AND NODE:
#
def initializePlugin(obj):
    plugin = om.MFnPlugin(obj)
    try:
        plugin.registerNode("ClothNode", ClothNode.id, ClothNode.cmdCreator, ClothNode.initialize)
    except:
        sys.stderr.write("Failed to register node\n")
        raise

#
# UNINITIALIZES THE PLUGIN BY DEREGISTERING THE COMMAND AND NODE:
#
def uninitializePlugin(obj):
    plugin = om.MFnPlugin(obj)
    try:
        plugin.deregisterNode(ClothNode.id)
    except:
        sys.stderr.write("Failed to deregister node\n")
        raise

