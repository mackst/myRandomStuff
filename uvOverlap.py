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


# this script was base on MayaInstallDir/devkit/plug-ins/peltOverlapCmd/peltOverlapCmd.cpp
# using python API 2.0

# how to use:
# 
# from maya import cmds
# 
# pcube = cmds.polyCube()
# cmds.polyAutoProjection()
# cmds.polyEditUV('%s.map[12]' % pcube[0], u=-0.057, v=-0.109)
# overlapFaces = getOverlapUVFaces(pcube[0])
# cmds.select(overlapFaces, r=1)

import math
import maya.api.OpenMaya as om


def createBoundingCircle(meshfn):
    """Parameter: meshfn - MFnMesh
    Represent a face by a center and radius, i.e.
    center = [center1u, center1v, center2u, center2v, ... ]
    radius = [radius1, radius2,  ... ]
    
    return (center, radius)"""
    center = []
    radius = []
    for i in xrange(meshfn.numPolygons):
        # get uvs from face
        uarray = []
        varray = []
        for j in range(len(meshfn.getPolygonVertices(i))):
            uv = meshfn.getPolygonUV(i, j)
            uarray.append(uv[0])
            varray.append(uv[1])
        
        # loop through all vertices to construct edges/rays
        cu = .0
        cv = .0
        for j in range(len(uarray)):
            cu += uarray[j]
            cv += varray[j]
        
        cu /= len(uarray)
        cv /= len(varray)
        rsqr = .0
        for j in range(len(varray)):
            du = uarray[j] - cu
            dv = varray[j] - cv
            dsqr = du * du + dv * dv
            rsqr = dsqr if dsqr > rsqr else rsqr
            
        center.append(cu)
        center.append(cv)
        radius.append(math.sqrt(rsqr))
        
    return center, radius

def createRayGivenFace(meshfn, faceId):
    """Represent a face by a series of edges(rays), i.e.
    orig = [orig1u, orig1v, orig2u, orig2v, ... ]
    vec  = [vec1u,  vec1v,  vec2u,  vec2v,  ... ]
    
    return false if no valid uv's.
    return (true, orig, vec) or (false, None, None)"""
    orig = []
    vec = []
    # get uvs
    uarray = []
    varray = []
    for i in range(len(meshfn.getPolygonVertices(faceId))):
        uv = meshfn.getPolygonUV(faceId, i)
        uarray.append(uv[0])
        varray.append(uv[1])
    
    if len(uarray) == 0 or len(varray) == 0:
        return (False, None, None)
    
    # loop throught all vertices to construct edges/rays
    u = uarray[-1]
    v = varray[-1]
    for i in xrange(len(uarray)):
        orig.append(uarray[i])
        orig.append(varray[i])
        vec.append(u - uarray[i])
        vec.append(v - varray[i])
        u = uarray[i]
        v = varray[i]
    
    return (True, orig, vec)

def area(orig):
    sum = .0
    num = len(orig)/2
    for i in xrange(num):
        idx = 2 * i
        idy = (i + 1) % num
        idy = 2 * idy + 1
        idy2 = (i + num - 1) % num
        idy2 = 2 * idy2 + 1
        sum += orig[idx] * (orig[idy] - orig[idy2])
    
    return math.fabs(sum) * .5

def checkCrossingEdges(face1Orig, face1Vec, face2Orig, face2Vec):
    """Check if there are crossing edges between two faces. Return true 
    if there are crossing edges and false otherwise. A face is represented
    by a series of edges(rays), i.e. 
    faceOrig[] = [orig1u, orig1v, orig2u, orig2v, ... ]
    faceVec[]  = [vec1u,  vec1v,  vec2u,  vec2v,  ... ]"""
    face1Size = len(face1Orig)
    face2Size = len(face2Orig)
    for i in xrange(0, face1Size, 2):
        o1x = face1Orig[i]
        o1y = face1Orig[i+1]
        v1x = face1Vec[i]
        v1y = face1Vec[i+1]
        n1x = v1y
        n1y = -v1x
        for j in xrange(0, face2Size, 2):
            # Given ray1(O1, V1) and ray2(O2, V2)
            # Normal of ray1 is (V1.y, V1.x)
            o2x = face2Orig[j]
            o2y = face2Orig[j+1]
            v2x = face2Vec[j]
            v2y = face2Vec[j+1]
            n2x = v2y
            n2y = -v2x
            
            # Find t for ray2
            # t = [(o1x-o2x)n1x + (o1y-o2y)n1y] / (v2x * n1x + v2y * n1y)
            denum = v2x * n1x + v2y * n1y
            # Edges are parallel if denum is close to 0.
            if math.fabs(denum) < 0.000001: continue
            t2 = ((o1x-o2x)* n1x + (o1y-o2y) * n1y) / denum
            if (t2 < 0.00001 or t2 > 0.99999): continue
            
            # Find t for ray1
            # t = [(o2x-o1x)n2x + (o2y-o1y)n2y] / (v1x * n2x + v1y * n2y)
            denum = v1x * n2x + v1y * n2y
            # Edges are parallel if denum is close to 0.
            if math.fabs(denum) < 0.000001: continue
            t1 = ((o2x-o1x)* n2x + (o2y-o1y) * n2y) / denum
            
            # Edges intersect
            if (t1 > 0.00001 and t1 < 0.99999): return 1
        
    return 0

def getOverlapUVFaces(meshName):
    """Return overlapping faces"""
    faces = []
    # find polygon mesh node
    selList = om.MSelectionList()
    selList.add(meshName)
    mesh = selList.getDependNode(0)
    if mesh.apiType() == om.MFn.kTransform:
        dagPath = selList.getDagPath(0)
        dagFn = om.MFnDagNode(dagPath)
        child = dagFn.child(0)
        if child.apiType() != om.MFn.kMesh:
            raise Exception("Can't find polygon mesh")
        mesh = child
    meshfn = om.MFnMesh(mesh)
    
    center, radius = createBoundingCircle(meshfn)
    for i in xrange(meshfn.numPolygons):
        rayb1, face1Orig, face1Vec = createRayGivenFace(meshfn, i)
        if not rayb1: continue
        cui = center[2*i]
        cvi = center[2*i+1]
        ri = radius[i]
        # Exclude the degenerate face
        # if(area(face1Orig) < 0.000001) continue;
        # Loop through face j where j != i
        for j in range(i+1, meshfn.numPolygons):
            cuj = center[2*j]
            cvj = center[2*j+1]
            rj = radius[j]
            du = cuj - cui
            dv = cvj - cvi
            dsqr = du * du + dv * dv
            # Quick rejection if bounding circles don't overlap
            if (dsqr >= (ri + rj) * (ri + rj)): continue
            
            rayb2, face2Orig, face2Vec = createRayGivenFace(meshfn, j)
            if not rayb2: continue
            # Exclude the degenerate face
            # if(area(face2Orig) < 0.000001): continue;
            if checkCrossingEdges(face1Orig, face1Vec, face2Orig, face2Vec):
                face1 = '%s.f[%d]' % (meshfn.name(), i)
                face2 = '%s.f[%d]' % (meshfn.name(), j)
                if face1 not in faces:
                    faces.append(face1)
                if face2 not in faces:
                    faces.append(face2)
    return faces
