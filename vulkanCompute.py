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

import datetime
import maya.api.OpenMaya as om

import cffi
import numpy as np
from vulkan import *


mffi = cffi.FFI()
mffi.cdef('''
struct ubo {
int numVert;
float angle;
float envelope;
};
'''
)


class InstanceProcAddr(object):

    def __init__(self, func):
        self.__func = func

    def __call__(self, *args, **kwargs):
        funcName = self.__func.__name__
        func = vkGetInstanceProcAddr(args[0], funcName)
        if func:
            return func(*args, **kwargs)
        else:
            return VK_ERROR_EXTENSION_NOT_PRESENT

@InstanceProcAddr
def vkCreateDebugReportCallbackEXT(instance, pCreateInfo, pAllocator):
    pass

@InstanceProcAddr
def vkDestroyDebugReportCallbackEXT(instance, pCreateInfo, pAllocator):
    pass

def debugCallback(*args):
    print('DEBUG: {} {}'.format(args[5], args[6]))
    return 0

def findBestComputeQueue(physicalDevice):
    queueFamilyIndex = -1
    queueFamilyProperties = vkGetPhysicalDeviceQueueFamilyProperties(physicalDevice)

    #
    for i, queueFamily in enumerate(queueFamilyProperties):
        maskedFlags = ~(VK_QUEUE_TRANSFER_BIT | VK_QUEUE_SPARSE_BINDING_BIT) & queueFamily.queueFlags

        if not (VK_QUEUE_GRAPHICS_BIT & maskedFlags) and VK_QUEUE_COMPUTE_BIT & maskedFlags:
            queueFamilyIndex = i
            return queueFamilyIndex

    for i, queueFamily in enumerate(queueFamilyProperties):
        maskedFlags = ~(VK_QUEUE_TRANSFER_BIT | VK_QUEUE_SPARSE_BINDING_BIT) & queueFamily.queueFlags

        if VK_QUEUE_COMPUTE_BIT & maskedFlags:
            queueFamilyIndex = i
            return queueFamilyIndex

    return queueFamilyIndex

def findMemoryType(physicalDevice, typeFilter, properties):
    memProperties = vkGetPhysicalDeviceMemoryProperties(physicalDevice)

    for i, prop in enumerate(memProperties.memoryTypes):
        if (typeFilter & (1 << i)) and ((prop.propertyFlags & properties) == properties):
            return i

    return -1

def computeYTwistVulkan(meshName, shaderFile, angle=0.0, env=1.0, debug=False):

    selList = om.MSelectionList()
    selList.add(meshName)

    meshFn = om.MFnMesh(selList.getDagPath(0))

    allPos = meshFn.getPoints(om.MSpace.kWorld)

    ubo = mffi.new('struct ubo *', [meshFn.numVertices, angle, env])

    allPosArray = np.array(
        [list(i) for i in allPos],
        np.float32
    )

    del allPos

    # vulkan setup
    appInfo = VkApplicationInfo(
        pApplicationName='vulkan compute',
        applicationVersion=VK_MAKE_VERSION(1, 0, 0),
        pEngineName='maya py api 2.0',
        engineVersion=VK_MAKE_VERSION(1, 0, 0),
        apiVersion=VK_API_VERSION_1_0
    )

    extentionNames = ["VK_EXT_debug_report",]
    layerNames = ["VK_LAYER_LUNARG_standard_validation"]

    instanceInfo = VkInstanceCreateInfo(
        pApplicationInfo=appInfo,
        ppEnabledExtensionNames=extentionNames,
        enabledLayerCount=0
    )
    if debug:
        instanceInfo = VkInstanceCreateInfo(
            pApplicationInfo=appInfo,
            ppEnabledExtensionNames=extentionNames,
            ppEnabledLayerNames=layerNames
        )

    instance = vkCreateInstance(instanceInfo, None)

    debugcallback = None
    if debug:
        debugCallbackCreateInfo = VkDebugReportCallbackCreateInfoEXT(
            flags=VK_DEBUG_REPORT_WARNING_BIT_EXT | VK_DEBUG_REPORT_ERROR_BIT_EXT,
            pfnCallback=debugCallback
        )

        debugcallback = vkCreateDebugReportCallbackEXT(instance, debugCallbackCreateInfo, None)

    physicalDevice = vkEnumeratePhysicalDevices(instance)[0]

    queueFamilyIndex = findBestComputeQueue(physicalDevice)

    deviceQueueCreateInfo = VkDeviceQueueCreateInfo(
        queueFamilyIndex=queueFamilyIndex,
        queueCount=1,
        pQueuePriorities=[1.0,]
    )

    deviceCreateInfo = VkDeviceCreateInfo(
        pQueueCreateInfos=[deviceQueueCreateInfo,],
        enabledExtensionCount=0,
        enabledLayerCount=0
    )
    if debug:
        deviceCreateInfo = VkDeviceCreateInfo(
            pQueueCreateInfos=[deviceQueueCreateInfo, ],
            enabledExtensionCount=0,
            ppEnabledLayerNames=layerNames
        )

    device = vkCreateDevice(physicalDevice, deviceCreateInfo, None)

    bufferCreateInfo = VkBufferCreateInfo(
        size=allPosArray.nbytes,
        usage=VK_BUFFER_USAGE_STORAGE_BUFFER_BIT,
        sharingMode=VK_SHARING_MODE_EXCLUSIVE,
        pQueueFamilyIndices=[queueFamilyIndex,]
    )

    inBuffer = vkCreateBuffer(device, bufferCreateInfo, None)
    outBuffer = vkCreateBuffer(device, bufferCreateInfo, None)

    memRequirements = vkGetBufferMemoryRequirements(device, inBuffer)

    memIndex = findMemoryType(physicalDevice, memRequirements.memoryTypeBits, VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT | VK_MEMORY_PROPERTY_HOST_COHERENT_BIT)

    memoryAllocatInfo = VkMemoryAllocateInfo(
        allocationSize=memRequirements.size,
        memoryTypeIndex=memIndex
    )

    inMemory = vkAllocateMemory(device, memoryAllocatInfo, None)

    dataPtr = vkMapMemory(device, inMemory, 0, allPosArray.nbytes, 0)
    posPtr = ffi.cast('float*', allPosArray.ctypes.data)
    ffi.memmove(dataPtr, posPtr, allPosArray.nbytes)
    vkUnmapMemory(device, inMemory)

    memRequirements = vkGetBufferMemoryRequirements(device, outBuffer)
    memoryAllocatInfo.memoryTypeIndex = findMemoryType(physicalDevice, memRequirements.memoryTypeBits, VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT | VK_MEMORY_PROPERTY_HOST_COHERENT_BIT)

    outMemory = vkAllocateMemory(device, memoryAllocatInfo, None)

    vkBindBufferMemory(device, inBuffer, inMemory, 0)
    vkBindBufferMemory(device, outBuffer, outMemory, 0)

    uboBufferCreateInfo = VkBufferCreateInfo(
        size=mffi.sizeof(ubo[0]),
        usage=VK_BUFFER_USAGE_UNIFORM_BUFFER_BIT,
        sharingMode=VK_SHARING_MODE_EXCLUSIVE,
        pQueueFamilyIndices=[queueFamilyIndex,]
    )

    uboBuffer = vkCreateBuffer(device, uboBufferCreateInfo, None)
    memRequirements = vkGetBufferMemoryRequirements(device, uboBuffer)

    uboMemoryAllocInfo = VkMemoryAllocateInfo(
        allocationSize=memRequirements.size,
        memoryTypeIndex=findMemoryType(physicalDevice, memRequirements.memoryTypeBits, VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT | VK_MEMORY_PROPERTY_HOST_COHERENT_BIT)
    )

    uboMemory = vkAllocateMemory(device, uboMemoryAllocInfo, None)

    uboPtr = vkMapMemory(device, uboMemory, 0, mffi.sizeof(ubo[0]), 0)
    mffi.memmove(uboPtr, ubo, mffi.sizeof(ubo[0]))
    vkUnmapMemory(device, uboMemory)

    vkBindBufferMemory(device, uboBuffer, uboMemory, 0)

    with open(shaderFile, 'rb') as sf:
        shaderCode = sf.read()

    shaderModuleCreateInfo = VkShaderModuleCreateInfo(
        codeSize=len(shaderCode),
        pCode=shaderCode
    )

    shaderModule = vkCreateShaderModule(device, shaderModuleCreateInfo, None)

    descriptorSetLayoutBindings = [
        VkDescriptorSetLayoutBinding(
            binding=0,
            descriptorType=VK_DESCRIPTOR_TYPE_STORAGE_BUFFER,
            descriptorCount=1,
            stageFlags=VK_SHADER_STAGE_COMPUTE_BIT
        ),

        VkDescriptorSetLayoutBinding(
            binding=1,
            descriptorType=VK_DESCRIPTOR_TYPE_STORAGE_BUFFER,
            descriptorCount=1,
            stageFlags=VK_SHADER_STAGE_COMPUTE_BIT
        ),

        VkDescriptorSetLayoutBinding(
            binding=2,
            descriptorType=VK_DESCRIPTOR_TYPE_UNIFORM_BUFFER,
            descriptorCount=1,
            stageFlags=VK_SHADER_STAGE_COMPUTE_BIT
        )
    ]

    descriporSetLayoutCreateinfo = VkDescriptorSetLayoutCreateInfo(
        pBindings=descriptorSetLayoutBindings
    )

    descriptorSetLayout = vkCreateDescriptorSetLayout(device, descriporSetLayoutCreateinfo, None)

    descriptorPoolSize = VkDescriptorPoolSize(descriptorCount=3)
    descriptorPoolInfo = VkDescriptorPoolCreateInfo(
        maxSets=1,
        pPoolSizes=[descriptorPoolSize,]
    )
    descriptorPool = vkCreateDescriptorPool(device, descriptorPoolInfo, None)
    descriptorSetAllocateInfo = VkDescriptorSetAllocateInfo(
        descriptorPool=descriptorPool,
        pSetLayouts=[descriptorSetLayout,]
    )
    descriptorSet = vkAllocateDescriptorSets(device, descriptorSetAllocateInfo)[0]

    inBufferInfo = VkDescriptorBufferInfo(
        buffer=inBuffer,
        offset=0,
        range=allPosArray.nbytes
    )

    outBufferInfo = VkDescriptorBufferInfo(
        buffer=outBuffer,
        offset=0,
        range=allPosArray.nbytes
    )

    uboBufferInfo = VkDescriptorBufferInfo(
        buffer=uboBuffer,
        offset=0,
        range=mffi.sizeof(ubo[0])
    )

    writeDescriptorSets = [
        VkWriteDescriptorSet(
            dstSet=descriptorSet,
            dstBinding=0,
            dstArrayElement=0,
            descriptorCount=1,
            descriptorType=VK_DESCRIPTOR_TYPE_STORAGE_BUFFER,
            pBufferInfo=inBufferInfo
        ),

        VkWriteDescriptorSet(
            dstSet=descriptorSet,
            dstBinding=1,
            dstArrayElement=0,
            descriptorCount=1,
            descriptorType=VK_DESCRIPTOR_TYPE_STORAGE_BUFFER,
            pBufferInfo=outBufferInfo
        ),

        VkWriteDescriptorSet(
            dstSet=descriptorSet,
            dstBinding=2,
            dstArrayElement=0,
            descriptorCount=1,
            descriptorType=VK_DESCRIPTOR_TYPE_UNIFORM_BUFFER,
            pBufferInfo=uboBufferInfo
        )
    ]

    vkUpdateDescriptorSets(device, len(writeDescriptorSets), writeDescriptorSets, 0, None)

    pipelineLayoutInfo = VkPipelineLayoutCreateInfo(
        pSetLayouts=[descriptorSetLayout,]
    )
    pipelineLayout = vkCreatePipelineLayout(device, pipelineLayoutInfo, None)

    shaderStage = VkPipelineShaderStageCreateInfo(
        stage=VK_SHADER_STAGE_COMPUTE_BIT,
        module=shaderModule,
        pName='main'
    )

    pipelineInfo = VkComputePipelineCreateInfo(
        stage=shaderStage,
        layout=pipelineLayout
    )

    pipeline = vkCreateComputePipelines(device, None, 1, pipelineInfo, None)

    commandPoolInfo = VkCommandPoolCreateInfo(
        queueFamilyIndex=queueFamilyIndex
    )

    commandPool = vkCreateCommandPool(device, commandPoolInfo, None)

    commandBufferInfo = VkCommandBufferAllocateInfo(
        commandPool=commandPool,
        level=VK_COMMAND_BUFFER_LEVEL_PRIMARY,
        commandBufferCount=1
    )
    cmdBuffer = vkAllocateCommandBuffers(device, commandBufferInfo)[0]

    cmdBeginInfo = VkCommandBufferBeginInfo(
        flags=VK_COMMAND_BUFFER_USAGE_ONE_TIME_SUBMIT_BIT
    )

    vkBeginCommandBuffer(cmdBuffer, cmdBeginInfo)

    vkCmdBindPipeline(cmdBuffer, VK_PIPELINE_BIND_POINT_COMPUTE, pipeline)

    vkCmdBindDescriptorSets(cmdBuffer, VK_PIPELINE_BIND_POINT_COMPUTE, pipelineLayout, 0, 1, [descriptorSet,], 0, None)

    vkCmdDispatch(cmdBuffer, meshFn.numVertices, 1, 1)

    vkEndCommandBuffer(cmdBuffer)

    queue = vkGetDeviceQueue(device, queueFamilyIndex, 0)
    submitInfo = VkSubmitInfo(
        waitSemaphoreCount=0,
        pCommandBuffers=[cmdBuffer,],
        signalSemaphoreCount=0
    )
    vkQueueSubmit(queue, 1, submitInfo, None)
    vkQueueWaitIdle(queue)

    vkDestroyBuffer(device, inBuffer, None)
    vkFreeMemory(device, inMemory, None)

    newDataPtr = vkMapMemory(device, outMemory, 0, allPosArray.nbytes, 0)
    ffi.memmove(posPtr, newDataPtr, allPosArray.nbytes)
    vkUnmapMemory(device, outMemory)

    vkDestroyBuffer(device, outBuffer, None)
    vkFreeMemory(device, outMemory, None)

    # update position
    newPos = om.MPointArray(allPosArray.tolist())
    del allPosArray
    meshFn.setPoints(newPos, om.MSpace.kWorld)

    # clean up

    vkDestroyShaderModule(device, shaderModule, None)
    vkDestroyCommandPool(device, commandPool, None)
    vkDestroyDescriptorSetLayout(device, descriptorSetLayout, None)
    vkDestroyDescriptorPool(device, descriptorPool, None)
    vkDestroyPipelineLayout(device, pipelineLayout, None)
    vkDestroyPipeline(device, pipeline, None)
    vkDestroyBuffer(device, uboBuffer, None)
    vkFreeMemory(device, uboMemory, None)
    vkDestroyDevice(device, None)

    if debugcallback:
        vkDestroyDebugReportCallbackEXT(instance, debugcallback, None)

    vkDestroyInstance(instance, None)


spheres = cmds.polySphere()
startTime = datetime.datetime.now()
computeYTwistVulkan(spheres[0], "E:\\coding\\pythonProjects\\myRandomStuff\\plugins\\yTwistNode.spv", 20.0, 1.0, True)
print('----------------------- compute time: {}'.format(datetime.datetime.now() - startTime))

