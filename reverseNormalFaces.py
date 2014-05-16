# -*- coding: utf-8 -*-

# The MIT License (MIT)
#
# Copyright (c) 2014 Mack Stone
#
# Permission is hereby granted, free of charge, to any person obtaining a copy of
# this software and associated documentation files (the "Software"), to deal in
# the Software without restriction, including without limitation the rights to
# use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of
# the Software, and to permit persons to whom the Software is furnished to do so,
# subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS
# FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR
# COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER
# IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
# CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

# How to use it
#
# faces = getReversNormalFaces("pSphereShape1")
# cmds.select(faces, r=1)

import maya.api.OpenMaya as om

def getReverseNormalFaces(meshName):
    '''get reverse normal faces from given ploygon mesh base on uv projection.
    If the uv projection was not correct you may get uncorrect result'''
    revFaces = []
    selList = om.MSelectionList()
    selList.add(meshName)
    mesh = om.MFnMesh(selList.getDependNode(0))
    
    for fid in range(mesh.numPolygons):
        count = 0
        numVert = len(mesh.getPolygonVertices(fid))
        for i in range(numVert):
            j = (i + 1) % numVert
            k = (i + 2) % numVert
            uv1 = mesh.getPolygonUV(fid, i)
            uv2 = mesh.getPolygonUV(fid, j)
            uv3 = mesh.getPolygonUV(fid, k)
            v1 = om.MPoint(uv2[0], uv2[1]) - om.MPoint(uv1[0], uv1[1])
            v2 = om.MPoint(uv3[0], uv3[1]) - om.MPoint(uv1[0], uv1[1])
            w = v1 ^ v2
            if w.z > 0:
                count += 1
            elif w.z < 0:
                count -= 1
                
        if count < 0:
            revFaces.append('%s.f[%i]' % (meshName, fid))
            
    return revFaces