# --------------------------------------------------------------------------------
# Copyright (c) 2017 Shi Chi(Mack Stone). All rights reserved.
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

"""
Simple deform node use vulkan and compute shader in Maya.

@author: Shi Chi(Mack Stone)

To use this node:

cmds.loadPlugin("yTwistNode_vulkan.py")
cmds.polySphere()
cmds.deformer(type='yTwistNode')
"""

import os
import inspect
import logging

import maya.OpenMaya as om
import maya.OpenMayaMPx as ompx
import maya.cmds as cmds
from maya import utils

import cffi
from vulkan import *


_currentDir = os.path.dirname(os.path.abspath(inspect.getframeinfo(inspect.currentframe()).filename))

kApiVersion = cmds.about(apiVersion=True)
if kApiVersion < 201600:
    outputGeom = ompx.cvar.MPxDeformerNode_outputGeom
    envelope = ompx.cvar.MPxDeformerNode_envelope
else:
    outputGeom = ompx.cvar.MPxGeometryFilter_outputGeom
    envelope = ompx.cvar.MPxGeometryFilter_envelope


# shaders

computeShaderSrc = """#version 450

#extension GL_ARB_separate_shader_objects : enable
#extension GL_ARB_shading_language_420pack : enable

layout(local_size_x = 256) in;

layout(binding = 0) buffer InputBuffer{ vec4 inPos[]; };
layout(binding = 1) buffer OutputBuffer{ vec4 outPos[]; };

layout(binding = 2) uniform UBO{
int numVert;
float angle;
float envelope;
} ubo;

void main()
{
    uint index = gl_GlobalInvocationID.x;
    if (index >= ubo.numVert)
        return;

    vec4 pos = inPos[index];
    vec4 oPos = pos;
    float ff = ubo.angle * pos.y * ubo.envelope;
    if (ff != 0.0f)
    {
        float cct = cos(ff);
        float cst = sin(ff);
        oPos.x = pos.x * cct - pos.z * cst;
        oPos.z = pos.x * cst + pos.z * cct;
    }
    outPos[index] = oPos;
}
"""

mffi = cffi.FFI()
mffi.cdef('''
struct ubo {
int numVert;
float angle;
float envelope;
};
'''
)


def findBestTransferQueue(physicalDevice):
    queueFamilyIndex = -1
    queueFamilyProperties = vkGetPhysicalDeviceQueueFamilyProperties(physicalDevice)

    #
    for i, queueFamily in enumerate(queueFamilyProperties):
        maskedFlags = ~VK_QUEUE_SPARSE_BINDING_BIT & queueFamily.queueFlags

        if not ((VK_QUEUE_GRAPHICS_BIT | VK_QUEUE_COMPUTE_BIT) & maskedFlags) and VK_QUEUE_TRANSFER_BIT & maskedFlags:
            queueFamilyIndex = i
            return queueFamilyIndex

    for i, queueFamily in enumerate(queueFamilyProperties):
        maskedFlags = ~VK_QUEUE_SPARSE_BINDING_BIT & queueFamily.queueFlags

        if not (VK_QUEUE_GRAPHICS_BIT & maskedFlags) and VK_QUEUE_COMPUTE_BIT & maskedFlags:
            queueFamilyIndex = i
            return queueFamilyIndex

    for i, queueFamily in enumerate(queueFamilyProperties):
        maskedFlags = ~VK_QUEUE_SPARSE_BINDING_BIT & queueFamily.queueFlags

        if (VK_QUEUE_GRAPHICS_BIT | VK_QUEUE_COMPUTE_BIT | VK_QUEUE_TRANSFER_BIT) & maskedFlags:
            queueFamilyIndex = i
            return queueFamilyIndex

    return queueFamilyIndex

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

def computeData(inData, numVert, angle, envelope):
    outData = []
    memorySize = len(inData) * 4
    ubo = mffi.new('struct ubo *', [numVert, angle, envelope])

    logging.info('Create vulkan instance')
    appInfo = VkApplicationInfo(
        sType=VK_STRUCTURE_TYPE_APPLICATION_INFO,
        pApplicationName='ComputeSample',
        pEngineName='Compute',
        apiVersion=VK_MAKE_VERSION(1, 0, 9)
    )

    instanceInfo = VkInstanceCreateInfo(
        sType=VK_STRUCTURE_TYPE_INSTANCE_CREATE_INFO,
        pApplicationInfo=appInfo
    )

    instance = vkCreateInstance(instanceInfo, None)

    physicalDevices = vkEnumeratePhysicalDevices(instance)
    for physicalDevice in physicalDevices:
        queueFamilyIndex = findBestComputeQueue(physicalDevice)

        queuePrioritory = [1.0]
        deviceQueueCreateInfo = VkDeviceQueueCreateInfo(
            sType=VK_STRUCTURE_TYPE_DEVICE_QUEUE_CREATE_INFO,
            queueFamilyIndex=queueFamilyIndex,
            queueCount=1,
            pQueuePriorities=queuePrioritory
        )

        deviceCreateInfo = VkDeviceCreateInfo(
            sType=VK_STRUCTURE_TYPE_DEVICE_CREATE_INFO,
            queueCreateInfoCount=1,
            pQueueCreateInfos=deviceQueueCreateInfo,
            enabledLayerCount=0,
            enabledExtensionCount=0
        )

        logging.info('create device')
        device = vkCreateDevice(physicalDevice, deviceCreateInfo, None)

        properties = vkGetPhysicalDeviceMemoryProperties(physicalDevice)

        memoryTypeIndex = VK_MAX_MEMORY_TYPES

        for i, p in enumerate(properties.memoryTypes):
            if VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT & p.propertyFlags and VK_MEMORY_PROPERTY_HOST_COHERENT_BIT & p.propertyFlags:
                memoryTypeIndex = i
                break

        assert memoryTypeIndex != VK_MAX_MEMORY_TYPES

        logging.info('allocate memory')
        memoryAllocateInfo = VkMemoryAllocateInfo(
            sType=VK_STRUCTURE_TYPE_MEMORY_ALLOCATE_INFO,
            allocationSize=memorySize,
            memoryTypeIndex=memoryTypeIndex
        )

        memory = vkAllocateMemory(device, memoryAllocateInfo, None)

        dataBuffer = vkMapMemory(device, memory, 0, memorySize, 0)

        logging.info('fill data')
        cdata = ffi.new('float[]', inData)
        ffi.memmove(dataBuffer, cdata, memorySize)

        vkUnmapMemory(device, memory)

        logging.info('create buffer')
        bufferCreateInfo = VkBufferCreateInfo(
            sType=VK_STRUCTURE_TYPE_BUFFER_CREATE_INFO,
            size=memorySize,
            usage=VK_BUFFER_USAGE_STORAGE_BUFFER_BIT,
            sharingMode=VK_SHARING_MODE_EXCLUSIVE,
            queueFamilyIndexCount=1,
            pQueueFamilyIndices=queueFamilyIndex
        )

        in_buffer = vkCreateBuffer(device, bufferCreateInfo, None)

        vkBindBufferMemory(device, in_buffer, memory, 0)

        out_buffer = vkCreateBuffer(device, bufferCreateInfo, None)

        vkBindBufferMemory(device, out_buffer, memory, 0)

        # uniform buffer

        uboMemoryAllocateInfo = VkMemoryAllocateInfo(
            sType=VK_STRUCTURE_TYPE_MEMORY_ALLOCATE_INFO,
            allocationSize=mffi.sizeof(ubo[0]),
            memoryTypeIndex=memoryTypeIndex
        )

        uboMemory = vkAllocateMemory(device, uboMemoryAllocateInfo, None)
        uboData = vkMapMemory(device, uboMemory, 0, mffi.sizeof(ubo[0]), 0)

        ffi.memmove(uboData, ubo, mffi.sizeof(ubo[0]))
        vkUnmapMemory(device, uboMemory)

        uniformBufferCreateInfo = VkBufferCreateInfo(
            sType=VK_STRUCTURE_TYPE_BUFFER_CREATE_INFO,
            size=mffi.sizeof(ubo[0]),
            usage=VK_BUFFER_USAGE_UNIFORM_BUFFER_BIT,
            sharingMode=VK_SHARING_MODE_EXCLUSIVE,
            queueFamilyIndexCount=1,
            pQueueFamilyIndices=queueFamilyIndex
        )

        ubo_buffer = vkCreateBuffer(device, uniformBufferCreateInfo, None)
        vkBindBufferMemory(device, ubo_buffer, uboMemory, 0)

        logging.info('create shader module')
        compShader = os.path.join(_currentDir, 'yTwistNode.spv')
        shaderCode = ''
        with open(compShader, 'rb') as phile:
            shaderCode = phile.read()
        shaderModuleCreateInfo = VkShaderModuleCreateInfo(
            sType=VK_STRUCTURE_TYPE_SHADER_MODULE_CREATE_INFO,
            codeSize=len(shaderCode),
            pCode=shaderCode
        )

        shader_module = vkCreateShaderModule(device, shaderModuleCreateInfo, None)

        dslb1 = VkDescriptorSetLayoutBinding(
            binding=0,
            descriptorType=VK_DESCRIPTOR_TYPE_STORAGE_BUFFER,
            descriptorCount=1,
            stageFlags=VK_SHADER_STAGE_COMPUTE_BIT,
        )

        dslb2 = VkDescriptorSetLayoutBinding(
            binding=1,
            descriptorType=VK_DESCRIPTOR_TYPE_STORAGE_BUFFER,
            descriptorCount=1,
            stageFlags=VK_SHADER_STAGE_COMPUTE_BIT,
        )

        dslb3 = VkDescriptorSetLayoutBinding(
            binding=2,
            descriptorType=VK_DESCRIPTOR_TYPE_UNIFORM_BUFFER,
            descriptorCount=1,
            stageFlags=VK_SHADER_STAGE_COMPUTE_BIT,
        )
        descriptorSetLayoutBindings = [dslb1, dslb2, dslb3]

        descriptorSetLayoutCreateInfo = VkDescriptorSetLayoutCreateInfo(
            sType=VK_STRUCTURE_TYPE_DESCRIPTOR_SET_LAYOUT_CREATE_INFO,
            flags=0,
            bindingCount=len(descriptorSetLayoutBindings),
            pBindings=descriptorSetLayoutBindings
        )

        descriptorSetLayout = vkCreateDescriptorSetLayout(device, descriptorSetLayoutCreateInfo, None)

        pipelineLayoutCreateInfo = VkPipelineLayoutCreateInfo(
            sType=VK_STRUCTURE_TYPE_PIPELINE_LAYOUT_CREATE_INFO,
            flags=0,
            setLayoutCount=1,
            pSetLayouts=[descriptorSetLayout],
        )

        pipelineLayout = vkCreatePipelineLayout(device, pipelineLayoutCreateInfo, None)

        shaderStage = VkPipelineShaderStageCreateInfo(
            sType=VK_STRUCTURE_TYPE_PIPELINE_SHADER_STAGE_CREATE_INFO,
            flags=0,
            stage=VK_SHADER_STAGE_COMPUTE_BIT,
            module=shader_module,
            pName='main'
        )

        computePipelineCreateInfo = VkComputePipelineCreateInfo(
            sType=VK_STRUCTURE_TYPE_COMPUTE_PIPELINE_CREATE_INFO,
            flags=0,
            stage=shaderStage,
            layout=pipelineLayout
        )

        pipeline = vkCreateComputePipelines(device, None, 1, computePipelineCreateInfo, None)

        commandPoolCreateInfo = VkCommandPoolCreateInfo(
            sType=VK_STRUCTURE_TYPE_COMMAND_POOL_CREATE_INFO,
            queueFamilyIndex=queueFamilyIndex
        )

        descriptorPoolSize = VkDescriptorPoolSize(
            type=VK_DESCRIPTOR_TYPE_STORAGE_BUFFER,
            descriptorCount=3
        )

        descriptorPoolCreateInfo = VkDescriptorPoolCreateInfo(
            sType=VK_STRUCTURE_TYPE_DESCRIPTOR_POOL_CREATE_INFO,
            flags=0,
            maxSets=1,
            poolSizeCount=1,
            pPoolSizes=descriptorPoolSize
        )

        descriptorPool = vkCreateDescriptorPool(device, descriptorPoolCreateInfo, None)

        descriptorSetAllocateInfo = VkDescriptorSetAllocateInfo(
            sType=VK_STRUCTURE_TYPE_DESCRIPTOR_SET_ALLOCATE_INFO,
            descriptorPool=descriptorPool,
            descriptorSetCount=1,
            pSetLayouts=[descriptorSetLayout]
        )

        descriptorSet = vkAllocateDescriptorSets(device, descriptorSetAllocateInfo)

        in_descriptorBufferInfo = VkDescriptorBufferInfo(
            buffer=in_buffer,
            offset=0,
            range=ffi.cast('uint32_t', VK_WHOLE_SIZE)
        )

        out_descriptorBufferInfo = VkDescriptorBufferInfo(
            buffer=out_buffer,
            offset=0,
            range=ffi.cast('uint32_t', VK_WHOLE_SIZE)
        )

        ubo_descriptorBufferInfo = VkDescriptorBufferInfo(
            buffer=ubo_buffer,
            offset=0,
            # range=mffi.sizeof(ubo[0])
            range=ffi.cast('uint32_t', VK_WHOLE_SIZE)
        )

        wds1 = VkWriteDescriptorSet(
            sType=VK_STRUCTURE_TYPE_WRITE_DESCRIPTOR_SET,
            dstSet=descriptorSet[0],
            dstBinding=0,
            dstArrayElement=0,
            descriptorCount=1,
            descriptorType=VK_DESCRIPTOR_TYPE_STORAGE_BUFFER,
            pBufferInfo=ffi.addressof(in_descriptorBufferInfo)
        )

        wds2 = VkWriteDescriptorSet(
            sType=VK_STRUCTURE_TYPE_WRITE_DESCRIPTOR_SET,
            dstSet=descriptorSet[0],
            dstBinding=1,
            dstArrayElement=0,
            descriptorCount=1,
            descriptorType=VK_DESCRIPTOR_TYPE_STORAGE_BUFFER,
            pBufferInfo=ffi.addressof(out_descriptorBufferInfo)
        )

        wds3 = VkWriteDescriptorSet(
            sType=VK_STRUCTURE_TYPE_WRITE_DESCRIPTOR_SET,
            dstSet=descriptorSet[0],
            dstBinding=2,
            dstArrayElement=0,
            descriptorCount=1,
            descriptorType=VK_DESCRIPTOR_TYPE_UNIFORM_BUFFER,
            pBufferInfo=ffi.addressof(ubo_descriptorBufferInfo)
        )
        writeDescriptorSet = [wds1, wds2, wds3]

        vkUpdateDescriptorSets(device, len(writeDescriptorSet), writeDescriptorSet, 0, None)

        commandPool = vkCreateCommandPool(device, commandPoolCreateInfo, None)

        commandBufferAllocateInfo = VkCommandBufferAllocateInfo(
            sType=VK_STRUCTURE_TYPE_COMMAND_BUFFER_ALLOCATE_INFO,
            commandPool=commandPool,
            level=VK_COMMAND_BUFFER_LEVEL_PRIMARY,
            commandBufferCount=1
        )

        commandBuffer = vkAllocateCommandBuffers(device, commandBufferAllocateInfo)[0]

        commandBufferBeginInfo = VkCommandBufferBeginInfo(
            sType=VK_STRUCTURE_TYPE_COMMAND_BUFFER_BEGIN_INFO,
            flags=VK_COMMAND_BUFFER_USAGE_ONE_TIME_SUBMIT_BIT
        )

        vkBeginCommandBuffer(commandBuffer, commandBufferBeginInfo)

        vkCmdBindPipeline(commandBuffer, VK_PIPELINE_BIND_POINT_COMPUTE, pipeline)

        vkCmdBindDescriptorSets(commandBuffer, VK_PIPELINE_BIND_POINT_COMPUTE,
                                pipelineLayout, 0, 1, descriptorSet, 0, None)
        vkCmdDispatch(commandBuffer, numVert, 1, 1)

        vkEndCommandBuffer(commandBuffer)

        queue = vkGetDeviceQueue(device, queueFamilyIndex, 0)

        submitInfo = VkSubmitInfo(
            sType=VK_STRUCTURE_TYPE_SUBMIT_INFO,
            waitSemaphoreCount=0,
            commandBufferCount=1,
            pCommandBuffers=[commandBuffer]
        )

        vkQueueSubmit(queue, 1, submitInfo, None)
        vkQueueWaitIdle(queue)

        dataBuffer = vkMapMemory(device, memory, 0, memorySize, 0)
        # outData = [dataBuffer[i] for i in range(len(inData))]
        ffi.memmove(cdata, dataBuffer, memorySize)

        vkUnmapMemory(device, memory)

        logging.info('cleanup vulkan')
        vkDestroyShaderModule(device, shader_module, None)
        vkDestroyDescriptorSetLayout(device, descriptorSetLayout, None)
        vkDestroyPipelineLayout(device, pipelineLayout, None)
        vkDestroyPipeline(device, pipeline, None)
        vkFreeMemory(device, memory, None)
        vkDestroyDevice(device, None)

    del physicalDevices
    vkDestroyInstance(instance, None)

    # return outData
    return list(cdata)

class YTwistNode(ompx.MPxDeformerNode):
    
    NAME = "yTwistNode"
    ID = om.MTypeId(0x8702)
    
    angle = om.MObject()
    
    def __init__(self):
        ompx.MPxDeformerNode.__init__(self)
        
        # setup logger
        formatter = logging.Formatter("%(asctime)s - %(message)s")
        utils._guiLogHandler.setFormatter(formatter)

        
    def deform(self, dataBlock, geomIter, matrix, multiIndex):
        logging.info("start deforming")
        
        # get the angle from the datablock
        angleHandle = dataBlock.inputValue(self.angle)
        angleValue = angleHandle.asDouble()
        
        # get the envelope
        envelopeHandle = dataBlock.inputValue(envelope)
        envelopeValue = envelopeHandle.asFloat()
        
        # get all position data
        logging.info("get all position data")
        pos = []
        while not geomIter.isDone():
            point = geomIter.position()
            pos += [point.x, point.y, point.z, point.w]
            geomIter.next()
        
        #
        outPos = computeData(pos, geomIter.count(), angleValue, envelopeValue)
        newPos = [(outPos[i], outPos[i + 1], outPos[i + 2], outPos[i + 3]) for i in range(0, len(outPos), 4)]
        #print newPos
        #for i in newPos: print i
        
        # set positions
        logging.info("set all position")
        geomIter.reset()
        while not geomIter.isDone():
            point = geomIter.position()
            index = geomIter.index()
            
            point.x = newPos[index][0]
            point.y = newPos[index][1]
            point.z = newPos[index][2]
            geomIter.setPosition(point)
            geomIter.next()
            
        logging.info("end deform")
        
    @staticmethod
    def creator():
        return ompx.asMPxPtr(YTwistNode())
    
    @staticmethod
    def initialize():
        # angle
        nAttr = om.MFnNumericAttribute()
        YTwistNode.angle = nAttr.create("angle", "fa", om.MFnNumericData.kDouble, 0.0)
        nAttr.setKeyable(1)
        
        # add attribute
        YTwistNode.addAttribute(YTwistNode.angle)
        YTwistNode.attributeAffects(YTwistNode.angle, outputGeom)
        
# initialize the script plug-in
def initializePlugin(mobject):
    mplugin = ompx.MFnPlugin(mobject)
    try:
        mplugin.registerNode(YTwistNode.NAME, YTwistNode.ID, YTwistNode.creator, 
                             YTwistNode.initialize, ompx.MPxNode.kDeformerNode )
    except:
        sys.stderr.write("Failed to register node: %s\n" % YTwistNode.NAME)

# uninitialize the script plug-in
def uninitializePlugin(mobject):
    mplugin = ompx.MFnPlugin(mobject)
    try:
        mplugin.deregisterNode(YTwistNode.ID)
    except:
        sys.stderr.write("Failed to unregister node: %s\n" % YTwistNode.NAME )
