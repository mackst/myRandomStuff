import math
from maya import cmds


def clothDemo():
    clothNode = cmds.createNode('ClothNode')
    sphere, polySphere = cmds.polySphere()
    # plane, polyPlane = cmds.polyPlane(h=20., w=20., sh=20, sw=20, ax=(1., 0., 0.))
    plane, polyPlane = cmds.polyPlane(h=20., w=20., sh=100, sw=100, ax=(1., 0., 0.))
    planeShape = cmds.listRelatives(plane, c=1, s=1)[0]

    cmds.setAttr("{}.tx".format(sphere), 4)
    cmds.setAttr("{}.radius".format(polySphere), 5.5)
    # cmds.setAttr("{}.pinnedIdX".format(clothNode), 420)
    # cmds.setAttr("{}.pinnedIdY".format(clothNode), 440)
    # cmds.setAttr("{}.particleCountX".format(clothNode), 21)
    # cmds.setAttr("{}.particleCountY".format(clothNode), 21)

    cmds.setAttr("{}.pinnedIdX".format(clothNode), 10100)
    cmds.setAttr("{}.pinnedIdY".format(clothNode), 10200)
    cmds.setAttr("{}.particleCountX".format(clothNode), 101)
    cmds.setAttr("{}.particleCountY".format(clothNode), 101)

    cmds.setAttr("{}.visibility".format(plane), 0)

    multNode = cmds.createNode('multiplyDivide')
    cmds.setAttr("{}.operation".format(multNode), 2)
    plusNode = cmds.createNode('plusMinusAverage')
    cmds.setAttr("{}.operation".format(plusNode), 2)
    cmds.setAttr("{}.operation".format(plusNode), 2)
    cmds.connectAttr('{}.particleCountX'.format(clothNode), '{}.input2D[0].input2Dy'.format(plusNode), f=1)
    cmds.connectAttr('{}.particleCountY'.format(clothNode), '{}.input2D[0].input2Dx'.format(plusNode), f=1)
    cmds.setAttr("{}.input2D[1].input2Dx".format(plusNode), 1)
    cmds.setAttr("{}.input2D[1].input2Dy".format(plusNode), 1)
    cmds.connectAttr('{}.width'.format(polyPlane), '{}.input1X'.format(multNode), f=1)
    cmds.connectAttr('{}.height'.format(polyPlane), '{}.input1Y'.format(multNode), f=1)
    cmds.connectAttr('{}.translate'.format(sphere), '{}.spherePosition'.format(clothNode), f=1)
    cmds.connectAttr('{}.radius'.format(polySphere), '{}.sphereRadius'.format(clothNode), f=1)
    cmds.connectAttr('{}.output2Dx'.format(plusNode), '{}.input2X'.format(multNode), f=1)
    cmds.connectAttr('{}.output2Dy'.format(plusNode), '{}.input2Y'.format(multNode), f=1)
    cmds.connectAttr('{}.outputX'.format(multNode), '{}.restDistH'.format(clothNode), f=1)
    cmds.connectAttr('{}.outputY'.format(multNode), '{}.restDistV'.format(clothNode), f=1)

    restDistH = cmds.getAttr('{}.restDistH'.format(clothNode))
    restDistV = cmds.getAttr('{}.restDistV'.format(clothNode))
    restDistD = math.sqrt(restDistH * restDistH + restDistV + restDistV)
    cmds.setAttr('{}.restDistD'.format(clothNode), restDistD)

    clothMesh = cmds.createNode('mesh')
    cmds.connectAttr('{}.outMesh'.format(clothNode), '{}.inMesh'.format(clothMesh))

    # cmds.connectAttr('{}.worldMesh[0]'.format(polyPlane), '{}.inMesh'.format(clothNode), f=1)
    cmds.connectAttr('{}.outMesh'.format(planeShape), '{}.inMesh'.format(clothNode), f=1)


clothDemo()
