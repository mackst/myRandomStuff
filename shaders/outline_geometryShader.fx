/*
The MIT License (MIT)

Copyright (c) 2014 Mack Stone

Permission is hereby granted, free of charge, to any person obtaining a copy of
this software and associated documentation files (the "Software"), to deal in
the Software without restriction, including without limitation the rights to
use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of
the Software, and to permit persons to whom the Software is furnished to do so,
subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS
FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR
COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER
IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
*/



float4x4 world  : World      < string UIWidget = "None"; >;
float4x4 view   : View       < string UIWidget = "None"; >;
float4x4 proj   : Projection < string UIWidget = "None"; >;

// parameters section
float3 outlineColor : Diffuse
<
    string UIName = "Outline Color";
> = {.5f, .5f, .5f};


//------------------------------------
// Structs
//------------------------------------
// input from application
struct APPDATA
{
    float4 position  :  POSITION;
    //float3 normal    :  NORMAL;
};

// output to geometry and pixel shader
struct GSPS_INPUT
{
    float4 position      :  SV_Position;
    //float3 worldNormal   :  TEXCOORD0;
};


//------------------------------------
// vertex shader
//------------------------------------
GSPS_INPUT vShader(APPDATA IN)
{
    GSPS_INPUT OUT;
    OUT.position = mul(IN.position, world);
    OUT.position = mul(OUT.position, view);
    
    return OUT;
}


//------------------------------------
// geometry shader
//------------------------------------
[maxvertexcount(32)]
void gShader(triangleadj GSPS_INPUT input[6], inout LineStream<GSPS_INPUT> lineStream)
{
    GSPS_INPUT OUT;
    
    float3 V0 = input[0].position.xyz;
    float3 V1 = input[1].position.xyz;
    float3 V2 = input[2].position.xyz;
    float3 V3 = input[3].position.xyz;
    float3 V4 = input[4].position.xyz;
    float3 V5 = input[5].position.xyz;
    
    float3 N042 = cross(V4 - V0, V2 - V0);
    float3 N021 = cross(V2 - V0, V1 - V0);
    float3 N243 = cross(V4 - V2, V3 - V2);
    float3 N405 = cross(V0 - V4, V5 - V4);
    
    // rashly assume all 4 normals are really meant to be
    // within 90 degrees of each other
    if (dot(N042, N021) < 0.)
        N021 = -N021;
    
    if (dot(N042, N243) < 0.)
        N243 = -N243;
        
    if (dot(N042, N405) < 0.)
        N405 = -N405;
        
    // look for a silhouette edge between triangles 042 and 021
    if (N042.z * N021.z < 0.)
    {
        OUT.position = mul(float4(V0, 1.0), proj);
        lineStream.Append(OUT);
        
        OUT.position = mul(float4(V2, 1.0), proj);
        lineStream.Append(OUT);
        
        lineStream.RestartStrip();
    }
    
    // look for a silhouette edge between triangles 042 and 243
    if (N042.z * N243.z < 0.)
    {
        OUT.position = mul(float4(V2, 1.0), proj);
        lineStream.Append(OUT);
        
        OUT.position = mul(float4(V4, 1.0), proj);
        lineStream.Append(OUT);
        
        lineStream.RestartStrip();
    }
    
    // look for a silhouette edge between triangles 042 and 405
    if (N042.z * N405.z < 0.)
    {
        OUT.position = mul(float4(V4, 1.0), proj);
        lineStream.Append(OUT);
        
        OUT.position = mul(float4(V0, 1.0), proj);
        lineStream.Append(OUT);
        
        lineStream.RestartStrip();
    }
}


//------------------------------------
// pixel shader
//------------------------------------
float4 pShader(GSPS_INPUT IN) : COLOR
{
    float4 outColor = float4(outlineColor, 1.0);
    return outColor;
}

technique11 Simple
{
    pass one
    {
        SetVertexShader(CompileShader(vs_5_0, vShader()));
        SetHullShader(NULL);
        SetDomainShader(NULL);
        SetGeometryShader(CompileShader(gs_5_0, gShader()));
        SetPixelShader(CompileShader(ps_5_0, pShader()));
    }
}