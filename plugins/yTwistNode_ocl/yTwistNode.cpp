//-
// ==========================================================================
// Copyright 1995,2006,2008 Autodesk, Inc. All rights reserved.
//
// Use of this software is subject to the terms of the Autodesk
// license agreement provided at the time of installation or download,
// or which otherwise accompanies this software in either electronic
// or hard copy form.
// ==========================================================================
//+
//
//  File: yTwist.cpp
//
//  Description:
//        Example implementation of a deformer. This node
//        twists the deformed vertices around the y-axis.
//
#define __CL_ENABLE_EXCEPTIONS

#include <string.h>
#include <maya/MIOStream.h>
#include <math.h>

#include <maya/MPxDeformerNode.h>
#include <maya/MItGeometry.h>

#include <maya/MTypeId.h> 
#include <maya/MPlug.h>
#include <maya/MDataBlock.h>
#include <maya/MDataHandle.h>

#include <maya/MFnNumericAttribute.h>
#include <maya/MFnPlugin.h>
#include <maya/MFnDependencyNode.h>

#include <maya/MPointArray.h>
#include <maya/MPoint.h>
#include <maya/MMatrix.h>
#include <maya/MGlobal.h>

// opencl include
#include <CL/cl.hpp>
#include <cstdio>
#include <cstdlib>
#include <iostream>


#define McheckErr(stat,msg)        \
    if ( MS::kSuccess != stat ) {   \
    cerr << msg;                \
    return MS::kFailure;        \
    }

// kerne code
const char kerneSrc[] = "#pragma OPENCL EXTENSION cl_khr_fp64: enable\n"
"__kernel void ytwist(__global const double4 *pos,\n"
"__global double4 *newPos,\n"
"double magnitude,\n"
"float envelope)\n"
"{\n"
"    int gid = get_global_id(0);\n"
"    newPos[gid] = pos[gid];\n"
"    float ff = magnitude * pos[gid].y * envelope;\n"
"    if (ff != 0.f)\n"
"    {\n"
"        float cct = cos(ff);\n"
"        float cst = sin(ff);\n"
"        newPos[gid].x = pos[gid].x * cct - pos[gid].z * cst;\n"
"        newPos[gid].z = pos[gid].x * cst + pos[gid].z * cct;\n"
"    }\n"
"}";


class yTwist : public MPxDeformerNode
{
public:
    yTwist();
    virtual ~yTwist();

    static void* creator();
    static MStatus initialize();

    // deformation function
    //
    virtual MStatus deform(MDataBlock& block,
        MItGeometry& iter,
        const MMatrix& mat,
        unsigned int multiIndex);

public:
    // yTwist attributes
    //
    static MObject angle;  // angle to twist

    static MTypeId id;

private:

};

MTypeId yTwist::id(0x8000e);

////////////////////////
// yTwist attributes  //
////////////////////////

MObject yTwist::angle;


yTwist::yTwist()
//
//    Description:
//        constructor
//
{

}

yTwist::~yTwist()
//
//    Description:
//        destructor
//
{}

void* yTwist::creator()
//
//    Description:
//        create the yTwist
//
{
    return new yTwist();
}

MStatus yTwist::initialize()
//
//    Description:
//        initialize the attributes
//
{
    // local attribute initialization
    //
    MFnNumericAttribute nAttr;
    angle = nAttr.create("angle", "fa", MFnNumericData::kDouble);
    nAttr.setDefault(0.0);
    nAttr.setKeyable(true);
    addAttribute(angle);

    // affects
    //
    attributeAffects(yTwist::angle, yTwist::outputGeom);

    return MS::kSuccess;
}

MStatus
yTwist::deform(MDataBlock& block,
MItGeometry& iter,
const MMatrix& /*m*/,
unsigned int /*multiIndex*/)
//
// Method: deform
//
// Description:   Deform the point with a yTwist algorithm
//
// Arguments:
//   block      : the datablock of the node
//   iter       : an iterator for the geometry to be deformed
//   m          : matrix to transform the point into world space
//   multiIndex : the index of the geometry that we are deforming
//
//
{
    cl_int err = CL_SUCCESS;
    MStatus status = MS::kSuccess;

    // determine the angle of the yTwist
    //
    MDataHandle angleData = block.inputValue(angle, &status);
    McheckErr(status, "Error getting angle data handle\n");
    double magnitude = angleData.asDouble();

    // determine the envelope (this is a global scale factor)
    //
    MDataHandle envData = block.inputValue(envelope, &status);
    McheckErr(status, "Error getting envelope data handle\n");
    float env = envData.asFloat();

    try
    {
        // find a opencl platform
        std::vector<cl::Platform> platforms;
        cl::Platform::get(&platforms);
        if (platforms.size() == 0)
        {
            MGlobal::displayError("Platform size 0");
            return MS::kFailure;
        }

        // create a context
        cl_context_properties properties[] = { CL_CONTEXT_PLATFORM,
            (cl_context_properties)(platforms[0])(), 0 };
        cl::Context context(CL_DEVICE_TYPE_GPU, properties);
        // get devices
        std::vector<cl::Device> devices = context.getInfo<CL_CONTEXT_DEVICES>();
        // create a program
        cl::Program::Sources source(1, std::make_pair(kerneSrc, strlen(kerneSrc)));
        cl::Program program(context, source);
        program.build(devices);

        // position data
        int numPoints = iter.count();
        cl_double4 *allPos = new cl_double4[numPoints];
        cl_double4 *outPos = new cl_double4[numPoints];

        // iterate through each point in the geometry
        // get all position data
        int i = 0;
        for (; !iter.isDone(); iter.next()) {
            MPoint pt = iter.position();
            #if defined(__GNUC__)
            allPos[i].x = pt.x;
            allPos[i].y = pt.y;
            allPos[i].z = pt.z;
            allPos[i].w = pt.w;
            #else
            // for MSVC
            allPos[i].s[0] = pt.x;
            allPos[i].s[1] = pt.y;
            allPos[i].s[2] = pt.z;
            allPos[i].s[3] = pt.w;
            #endif

            i++;
        }

        // create buffers
        cl::Buffer posBuffer = cl::Buffer(context,
            CL_MEM_READ_ONLY | CL_MEM_COPY_HOST_PTR,
            numPoints * sizeof(cl_double4), allPos);
        cl::Buffer nposBuffer = cl::Buffer(context,
            CL_MEM_WRITE_ONLY | CL_MEM_USE_HOST_PTR,
            numPoints * sizeof(cl_double4), outPos);

        // create a kernel
        cl::Kernel kernel(program, "ytwist", &err);
        // set kernel argmuments
        kernel.setArg(0, posBuffer);
        kernel.setArg(1, nposBuffer);
        kernel.setArg(2, magnitude);
        kernel.setArg(3, env);

        // create a command queue
        cl::Event event;
        cl::CommandQueue queue(context, devices[0], 0, &err);
        // execut the kernel
        queue.enqueueNDRangeKernel(kernel,
            cl::NullRange,
            cl::NDRange(numPoints),
            cl::NullRange,
            NULL,
            &event);
        event.wait();

        // read the data back
        queue.enqueueReadBuffer(nposBuffer, CL_TRUE, 0, numPoints * sizeof(cl_double4), outPos);

        // set the new positions
        i = 0;
        iter.reset();
        for (; !iter.isDone(); iter.next()) {
            MPoint pt = iter.position();
            pt.x = outPos[i].s[0];
            pt.z = outPos[i].s[2];
            iter.setPosition(pt);
            i++;
        }

        // clean up
        delete[] allPos;
        delete[] outPos;
    }
    catch (cl::Error err){
        MString errStr;
        errStr += "ERROR: ";
        errStr += err.what();
        errStr += "(";
        errStr += err.err();
        errStr += ")";
        MGlobal::displayError(errStr);
        /*std::cerr << "ERROR: "
            << err.what()
            << "("
            << err.err()
            << ")"
            << std::endl;*/
    }

    return status;
}

// standard initialization procedures
//

MStatus initializePlugin(MObject obj)
{
    MStatus result;
    MFnPlugin plugin(obj, PLUGIN_COMPANY, "3.0", "Any");
    result = plugin.registerNode("yTwist", yTwist::id, yTwist::creator,
        yTwist::initialize, MPxNode::kDeformerNode);
    return result;
}

MStatus uninitializePlugin(MObject obj)
{
    MStatus result;
    MFnPlugin plugin(obj);
    result = plugin.deregisterNode(yTwist::id);
    return result;
}
