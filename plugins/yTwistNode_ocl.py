# --------------------------------------------------------------------------------
# Copyright (c) 2013 Mack Stone. All rights reserved.
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
Simple deform node use pyopencl in Maya.

@author: Mack Stone
"""

import sys
import logging

import maya.OpenMaya as om
import maya.OpenMayaMPx as ompx
from maya import utils

import numpy
import pyopencl as cl


# opencl code, run on GPU
kernelCode = """
__kernel void ytwist(__global const float4 *pos, 
                    __global float4 *newPos, 
                    float angle, 
                    float envelope)
{
    int gid = get_global_id(0);
    
    newPos[gid].xyzw = pos[gid].xyzw;
    
    float ff = angle * pos[gid].y * envelope;
    if(ff != 0.0f)
    {
        float cct = cos(ff);
        float cst = sin(ff);
        newPos[gid].x = pos[gid].x * cct - pos[gid].z * cst;
        newPos[gid].z = pos[gid].x * cst + pos[gid].z * cct;
    }
}
"""

class YTwistNode(ompx.MPxDeformerNode):
    
    NAME = "yTwistNode"
    ID = om.MTypeId(0x8702)
    
    angle = om.MObject()
    
    def __init__(self):
        ompx.MPxDeformerNode.__init__(self)
        
        # create context
        self._ctx = cl.create_some_context()
        # command queue
        self._queue = cl.CommandQueue(self._ctx)
        # create and build GPU program
        self._program = cl.Program(self._ctx, kernelCode).build()
        
        # setup logger
        formatter = logging.Formatter("%(asctime)s - %(message)s")
        utils._guiLogHandler.setFormatter(formatter)
        
    def deform(self, dataBlock, geomIter, matrix, multiIndex):
        logging.info("start deforming")
        
        # get the angle from the datablock
        angleHandle = dataBlock.inputValue( self.angle )
        angleValue = angleHandle.asDouble()
        
        # get the envelope
        envelope = OpenMayaMPx.cvar.MPxDeformerNode_envelope
        envelopeHandle = dataBlock.inputValue( envelope )
        envelopeValue = envelopeHandle.asFloat()
        
        # get all position data
        logging.info("get all position data")
        pos = numpy.zeros((geomIter.count(), 4), dtype=numpy.float32)
        while not geomIter.isDone():
            point = geomIter.position()
            index = geomIter.index()
            
            pos[index, 0] = point.x
            pos[index, 1] = point.y
            pos[index, 2] = point.z
            pos[index, 3] = point.w
            geomIter.next()
        
        logging.info("start copy data to GPU")
        memf = cl.mem_flags
        # create buffer from pos
        posBuf = cl.Buffer(self._ctx, memf.READ_ONLY | memf.COPY_HOST_PTR, hostbuf=pos)
        # create write buffer
        outBuf = cl.Buffer(self._ctx, memf.WRITE_ONLY, pos.nbytes)
        
        # run GPU Program 
        logging.info("run GPU Program")
        self._program.ytwist(self._queue, pos.shape, None, posBuf, outBuf, 
                             numpy.float32(angleValue), numpy.float32(envelopeValue))
        logging.info("end GPU Program")
        
        # copy data back to memory
        newPos = numpy.zeros_like(pos)
        cl.enqueue_copy(self._queue, newPos, outBuf).wait()
        
        # set positions
        logging.info("set all position")
        geomIter.reset()
        while not geomIter.isDone():
            point = geomIter.position()
            index = geomIter.index()
            
            point.x = float(newPos[index, 0])
            point.y = float(newPos[index, 1])
            point.z = float(newPos[index, 2])
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
        outputGeom = ompx.cvar.MPxDeformerNode_outputGeom
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
