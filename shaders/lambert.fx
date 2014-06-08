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


//------------------------------------
// Per Frame parameters
//------------------------------------
cbuffer UpdatePerFrame : register(b0)
{
    float4x4 viewPrj       : ViewProjection    < string UIWidget = "None"; >;
    float4x4 viewInverse   : ViewInverse         < string UIWidget = "None"; >;
    bool IsSwatchRender    : MayaSwatchRender  < string UIWidget = "None"; > = false;

    // If the user enables viewport gamma correction in Maya's global viewport rendering 
    // settings, the shader should not do gamma again
    bool MayaFullScreenGamma : MayaGammaCorrection < string UIWidget = "None"; > = false;
}

//------------------------------------
// Per Object parameters
//------------------------------------
cbuffer UpdatePerObject : register(b1)
{
    float4x4 world                 : World                   < string UIWidget = "None"; >;
    float4x4 wvp                   : WorldViewProjection     < string UIWidget = "None"; >;
    float4x4 worldInverseTranspose : WorldInverseTranspose   < string UIWidget = "None"; >;
    
    // parameters section
    float3 diffuseColor : Diffuse
    <
        string UIName = "Diffuse Color";
    > = {1.0f, 1.0f, 1.0f};
    
    float3 ambientColor : Diffuse
    <
        string UIName = "Ambient Color";
    > = {0.1f, 0.1f, 0.1f};
    
    // light direction
    float3 lightDirection : Direction
    <
        string UIName = "Light Direction";
        string Space = "World"; // using world space
    > = {0.0f, 1.0f, 0.0f};
}


//------------------------------------
// Structs
//------------------------------------
// input from application
struct APPDATA
{
    float4 position  :  POSITION;
    float3 normal    :  NORMAL;
};

// output to pixel shader
struct SHADERDATA
{
    float4 position      :  SV_Position;
    float3 worldNormal   :  TEXCOORD0;
};


//------------------------------------
// vertex shader
//------------------------------------
SHADERDATA vShader(APPDATA IN)
{
    SHADERDATA OUT;
    OUT.position = mul(IN.position, wvp);
    OUT.worldNormal = mul(IN.normal, worldInverseTranspose);
    
    return OUT;
}


//------------------------------------
// pixel shader
//------------------------------------
float4 pShader(SHADERDATA IN) : COLOR
{
    float4 outColor;
    
    float3 worldNormal = normalize(IN.worldNormal);
    float3 lightDir = normalize(-lightDirection);
    
    float3 lambert = saturate(dot(lightDir, worldNormal));
    
    outColor.rgb = diffuseColor * (ambientColor + lambert);
    outColor.a = 1.0f;
    
    return outColor;
}

technique11 Simple
{
    pass one
    {
        SetVertexShader(CompileShader(vs_5_0, vShader()));
        SetHullShader(NULL);
        SetDomainShader(NULL);
        SetGeometryShader(NULL);
        SetPixelShader(CompileShader(ps_5_0, pShader()));
    }
}