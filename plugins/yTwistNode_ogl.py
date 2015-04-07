# --------------------------------------------------------------------------------
# Copyright (c) 2014 Mack Stone. All rights reserved.
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
Simple deform node use pyopengl and compute shader in Maya.

@author: Mack Stone
"""

import sys
import ctypes
from array import array
import logging

import maya.OpenMaya as om
import maya.OpenMayaMPx as ompx
from maya import utils

import numpy as np
from OpenGL.GL import *
from OpenGL.GL import shaders
from PySide.QtOpenGL import *


# shaders

computeShaderSrc = """#version 430
layout(local_size_x = 256) in;

layout(std430, binding = 0) buffer InputBuffer{ vec4 inPos[]; };
layout(std430, binding = 1) buffer OutputBuffer{ vec4 outPos[]; };

uniform int numVert;
uniform float angle;
uniform float envelope;

void main()
{
    uint index = gl_GlobalInvocationID.x;
    if (index >= numVert)
        return;

    vec4 pos = inPos[index];
    vec4 oPos = pos;
    float ff = angle * pos.y * envelope;
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

class MyGLWidget(QGLWidget):
    
    def __init__(self, gformat, parent=None):
        super(MyGLWidget, self).__init__(gformat, parent)
        
        self.angle = 0.0
        self.envelope = 0.0
        self.vertexPos = None
        
        self.__program = None
        self.__fbo = None

        self.__data = None
        
    def paintGL(self):
        glClearColor(0, 0, 0, 0)
        
        # create shaders
        compShader = shaders.compileShader(computeShaderSrc, GL_COMPUTE_SHADER)
        # create shader program
        self.__program = shaders.compileProgram(compShader)
        
        # get attribute and set uniform for shaders
        glUseProgram(self.__program)
        self.numVertUL = glGetUniformLocation(self.__program, 'numVert')
        glUniform1i(self.numVertUL, len(self.vertexPos))
        self.angleUL = glGetUniformLocation(self.__program, 'angle')
        glUniform1f(self.angleUL, self.angle)
        self.envelopeUL = glGetUniformLocation(self.__program, 'envelope')
        glUniform1f(self.envelopeUL, self.envelope)
        #glUseProgram(0)
        
        # create buffers
        inPos, outPos = glGenBuffers(2)
        glBindBuffer(GL_SHADER_STORAGE_BUFFER, inPos)
        glBufferData(GL_SHADER_STORAGE_BUFFER, self.vertexPos.nbytes, self.vertexPos, GL_STATIC_DRAW)
        glBindBuffer(GL_SHADER_STORAGE_BUFFER, outPos)
        glBufferData(GL_SHADER_STORAGE_BUFFER, self.vertexPos.nbytes, np.zeros_like(self.vertexPos), GL_STATIC_DRAW)
        
        # bind buffers to fixed binding points
        glBindBufferBase(GL_SHADER_STORAGE_BUFFER, 0, inPos)
        glBindBufferBase(GL_SHADER_STORAGE_BUFFER, 1, outPos)

        # run compute shader
        glDispatchCompute(len(self.vertexPos), 1, 1)
        glMemoryBarrier(GL_SHADER_IMAGE_ACCESS_BARRIER_BIT | GL_SHADER_STORAGE_BARRIER_BIT 
                        | GL_BUFFER_UPDATE_BARRIER_BIT)

        glBindBuffer(GL_SHADER_STORAGE_BUFFER, outPos)
        dataBuffer = glMapBuffer(GL_SHADER_STORAGE_BUFFER, GL_READ_ONLY)
        data = ctypes.cast(dataBuffer, ctypes.POINTER(ctypes.c_float))
        self.__data = np.ctypeslib.as_array(data, (len(self.vertexPos), 4))
        glUnmapBuffer(GL_SHADER_STORAGE_BUFFER)
        
    def getData(self):
        return self.__data


class YTwistNode(ompx.MPxDeformerNode):
    
    NAME = "yTwistNode"
    ID = om.MTypeId(0x8702)
    
    angle = om.MObject()
    
    def __init__(self):
        ompx.MPxDeformerNode.__init__(self)
        
        # setup logger
        formatter = logging.Formatter("%(asctime)s - %(message)s")
        utils._guiLogHandler.setFormatter(formatter)

        gformat = QGLFormat()
        gformat.setVersion(4, 3)
        gformat.setProfile(QGLFormat.CoreProfile)
        self._widget = MyGLWidget(gformat)
        
    def deform(self, dataBlock, geomIter, matrix, multiIndex):
        logging.info("start deforming")
        
        # get the angle from the datablock
        angleHandle = dataBlock.inputValue(self.angle)
        angleValue = angleHandle.asDouble()
        
        # get the envelope
        envelope = ompx.cvar.MPxDeformerNode_envelope
        envelopeHandle = dataBlock.inputValue(envelope)
        envelopeValue = envelopeHandle.asFloat()
        
        # get all position data
        logging.info("get all position data")
        pos = np.zeros((geomIter.count(), 4), dtype=np.float32)
        while not geomIter.isDone():
            point = geomIter.position()
            index = geomIter.index()
            
            pos[index, 0] = point.x
            pos[index, 1] = point.y
            pos[index, 2] = point.z
            pos[index, 3] = point.w
            geomIter.next()
        
        # 
        self._widget.angle = angleValue
        self._widget.envelope = envelopeValue
        self._widget.vertexPos = pos
        self._widget.updateGL()
        newPos = self._widget.getData()
        #print newPos
        #for i in newPos: print i
        
        # set positions
        logging.info("set all position")
        geomIter.reset()
        while not geomIter.isDone():
            point = geomIter.position()
            index = geomIter.index()
            
            point.x = float(newPos[index, 0])
            point.y = float(newPos[index, 1])
            point.z = float(newPos[index, 2])
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
