import math

import maya.api.OpenMaya as om
import maya.OpenMaya as oom

from maya import cmds

class RayArrow(object):

    def __init__(self):
        self.botHandle = None
        self.topHandle = None
        self.__arrowMesh = None

        self.create()
        self.moveToGroup()

    def create(self):
        handle = cmds.polyCylinder(sc=0, r=0.05, sa=5)
        arrowCone = cmds.polyCone(r=.25, h=.5, sa=5)
        cmds.move(0, 1.2, 0)

        arrow = cmds.polyUnite(handle[0], arrowCone[0])
        arrow = cmds.rename(arrow[0], 'arrowMesh#')
        self.__arrowMesh = arrow

        cmds.DeleteHistory()

        topVertices = []
        botVertices = []
        selList = om.MSelectionList()
        selList.add(arrow)

        # meshFn = om.MFnMesh(selList.getDagPath(0))
        # for i in range(meshFn.numVertices):
        #     point = meshFn.getPoint(i, om.MSpace.kWorld)

        vertIt = om.MItMeshVertex(selList.getDagPath(0))
        while not vertIt.isDone():
            pos = vertIt.position(om.MSpace.kWorld)
            if pos.y > 0:
                topVertices.append(vertIt.index())
            else:
                botVertices.append(vertIt.index())
            vertIt.next()

        topVert = ['{}.vtx[{}]'.format(arrow, id) for id in topVertices]
        botVert = ['{}.vtx[{}]'.format(arrow, id) for id in botVertices]
        self.topHandle = cmds.cluster(topVert)[1]
        self.botHandle = cmds.cluster(botVert)[1]

        self.topHandle = cmds.rename(self.topHandle, 'arrowTopHandle#')
        self.botHandle = cmds.rename(self.botHandle, 'arrowbotHandle#')


    def orient(self):
        constraint = cmds.aimConstraint(self.botHandle, self.topHandle,
                                        aimVector=[0, -1, 0],
                                        upVector=[1, 0, 0])
        cmds.delete(constraint)
        constraint = cmds.aimConstraint(self.topHandle, self.botHandle,
                                        aimVector=[0, 1, 0],
                                        upVector=[1, 0, 0])
        cmds.delete(constraint)

    def moveToGroup(self):
        grpName = 'arrows'
        if not cmds.objExists(grpName):
            grp = cmds.group(em=1, n=grpName)
        else:
            grp = grpName

        cmds.parent(self.topHandle, grp)
        cmds.parent(self.botHandle, grp)
        cmds.parent(self.__arrowMesh, grp)


def getLightDirection(name):
    selList = oom.MSelectionList()
    selList.add(name)

    lightDagPath = oom.MDagPath()
    selList.getDagPath(0, lightDagPath)

    lightFn = oom.MFnSpotLight(lightDagPath)

    rayDir = lightFn.lightDirection(0, oom.MSpace.kWorld)

    return om.MFloatVector(rayDir)

def intersect():
    activeSelList = om.MGlobal.getActiveSelectionList()
    selListIt = om.MItSelectionList(activeSelList)

    sportLightTransformNode = None
    # spotLightDP = None
    # meshTransformNode = None
    meshDP = None

    while not selListIt.isDone():
        nodeDP = selListIt.getDagPath()
        if nodeDP.apiType() == om.MFn.kTransform:
            dagNodeFn = om.MFnDagNode(nodeDP)
            nodeDP = dagNodeFn.child(0)

        if nodeDP.apiType() == om.MFn.kSpotLight:
            # spotLightDP = nodeDP
            sportLightTransformNode = dagNodeFn
        elif nodeDP.apiType() == om.MFn.kMesh:
            meshDP = nodeDP
            # meshTransformNode = dagNodeFn
        selListIt.next()

    tx = sportLightTransformNode.findPlug('tx', False).asFloat()
    ty = sportLightTransformNode.findPlug('ty', False).asFloat()
    tz = sportLightTransformNode.findPlug('tz', False).asFloat()

    fpSource = om.MFloatPoint(tx, ty, tz)
    fvRayDir = getLightDirection(sportLightTransformNode.name())

    meshFn = om.MFnMesh(om.MDagPath.getAPathTo(meshDP))
    mmAccelParams = meshFn.autoUniformGridParams()
    hitPoint, hitRayParam, hitFace, hitTriangle, hitBary1, hitBary2 = meshFn.anyIntersection(
        fpSource, fvRayDir, om.MSpace.kWorld, 9999., False,
        accelParams=mmAccelParams, tolerance=float(1e-6))

    if hitRayParam == 0.0:
        print('There were no intersection points detected')
        return

    hitPoints, hitRayParams, hitFaces, hitTriangles, hitBary1s, hitBary2s = meshFn.allIntersections(
        fpSource, fvRayDir, om.MSpace.kWorld, 9999., False, tolerance=0.000001
    )

    normals = meshFn.getNormals(om.MSpace.kWorld)
    i = 0
    for hp in hitPoints:
        arrow = RayArrow()
        constraint = cmds.pointConstraint(sportLightTransformNode.name(), arrow.botHandle)
        cmds.delete(constraint)
        cube = cmds.polyCube()
        cmds.move(hp.x, hp.y, hp.z, ws=1)
        constraint = cmds.pointConstraint(cube[0], arrow.topHandle)
        cmds.delete(cube+constraint)
        arrow.orient()

        # reflection
        # R = 2(N dot L)N - L
        # L: fvRayDir
        faceId = hitFaces[i]

        # N
        faceNormal = normals[meshFn.getFaceNormalIds(faceId)[0]]

        # R
        refl = 2 * (faceNormal * fvRayDir) * faceNormal - fvRayDir

        # reflection arrow
        arrowRefl = RayArrow()
        constraint = cmds.pointConstraint(arrow.topHandle, arrowRefl.botHandle)
        cmds.delete(constraint)

        selListIt = om.MSelectionList()
        selListIt.add(arrowRefl.botHandle)
        selListIt.add(arrowRefl.topHandle)

        # move and rotate botHandle
        reflBotTran = om.MFnTransform(selListIt.getDagPath(0))
        reflBotTran.setRotation(om.MEulerRotation(refl), om.MSpace.kTransform)

        # move and rotate topHandle
        constraint = cmds.parentConstraint(arrowRefl.botHandle, arrowRefl.topHandle, mo=0)
        cmds.delete(constraint)
        # reflTopTran = om.MFnTransform(selListIt.getDagPath(1))
        # #reflTopTran.setRotation(om.MEulerRotation(refl), om.MSpace.kTransform)
        # # topMove = om.MVector(refl)
        # #topMove = om.MVector(refl + om.MFloatVector(0, 6, 0)) * reflTopTran.transformationMatrix()
        # topMove = om.MVector(refl * om.MFloatVector(1, 6, 1)) * reflBotTran.transformationMatrix()
        # # topMove.y += 6
        # reflTopTran.setTranslation(topMove, om.MSpace.kTransform)

        cmds.move(0, 6, 0, arrowRefl.topHandle, r=1, os=1, wd=1)

        arrowRefl.orient()

        # refraction arrow
        # T = ((1/fl*N) dot L) - sqrt(1 - 1/(fl*fl)*(1 - (N dot L)*(N dot L))) * N - 1/fl * L
        fl = .750
        fl2 = 0.5627813555039173

        a = (fl * faceNormal) * fvRayDir
        b = math.sqrt(1 - fl2 * abs(1 - math.pow(faceNormal * fvRayDir, 2)))
        c = a - b
        refr = c * faceNormal - fl * fvRayDir

        refrArrow = RayArrow()
        constraint = cmds.pointConstraint(arrow.topHandle, refrArrow.botHandle)
        cmds.delete(constraint)

        selListIt = om.MSelectionList()
        selListIt.add(refrArrow.botHandle)
        selListIt.add(refrArrow.topHandle)

        # move and rotate botHandle
        reflBotTran = om.MFnTransform(selListIt.getDagPath(0))
        reflBotTran.setRotation(om.MEulerRotation(refr), om.MSpace.kTransform)

        # move and rotate topHandle
        constraint = cmds.parentConstraint(refrArrow.botHandle, refrArrow.topHandle, mo=0)
        cmds.delete(constraint)

        cmds.move(0, -6, 0, refrArrow.topHandle, r=1, os=1, wd=1)

        refrArrow.orient()

        i += 1

def demo():
    cmds.file(f=1, new=1)
    cmds.polyPlane(w=50, h=50)
    cmds.rotate(1.555, -6.203, 6.393, r=1, os=1, fo=1)
    cmds.spotLight()
    cmds.move(14.142, 26.414, 18.0)
    cmds.rotate(-54, 36.4, 0, r=1, os=1, fo=1)
    if cmds.objExists('arrows'):
        cmds.delete('arrows')
    cmds.select(['pPlane1', 'spotLight1'])
    intersect()

demo()