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



float4x4 world                 : World                   < string UIWidget = "None"; >;
float4x4 wvp                   : WorldViewProjection     < string UIWidget = "None"; >;
float4x4 worldInverseTranspose : WorldInverseTranspose   < string UIWidget = "None"; >;

// parameters section
float3 frontColor : Diffuse
<
    string UIName = "Front Color";
> = {1.0f, 0.0f, 0.0f};

float3 backColor : Diffuse
<
    string UIName = "Back Color";
> = {0.f, 0.f, 1.f};

float discardU
<
    string UIWidget = "Slider";
    float UIMin = 0.0;
    float UIMax = 1.0;
    float UIStep = 0.001;
    string UIName = "Discard U";
> = .2f;

float discardV
<
    string UIWidget = "Slider";
    float UIMin = 0.0;
    float UIMax = 1.0;
    float UIStep = 0.001;
    string UIName = "Discard V";
> = .2f;


//------------------------------------
// Structs
//------------------------------------
// input from application
struct APPDATA
{
    float4 position  :  POSITION;
    float2 uv        :  TEXCOORD0;
};

// output to pixel shader
struct SHADERDATA
{
    float4 position  :  SV_Position;
    float2 uv        :  TEXCOORD0;
};


//------------------------------------
// vertex shader
//------------------------------------
SHADERDATA vShader(APPDATA IN)
{
    SHADERDATA OUT;
    OUT.uv = IN.uv;
    OUT.position = mul(IN.position, wvp);
    return OUT;
}


//------------------------------------
// pixel shader
//------------------------------------
float4 pShader(SHADERDATA IN, bool frontFace : SV_IsFrontFace) : COLOR
{
    float4 outColor;
    
    if (all(IN.uv < float2(discardU, discardV)))
        discard;
    else
    {
        if (frontFace)
            outColor.rgb = frontColor;
        else
            outColor.rgb = backColor;
        outColor.a = 1.0;
    }
    
    return outColor;
}

technique11 Simple
{
    pass one
    <
        string drawContext = "colorPass";
    >
    {
        SetVertexShader(CompileShader(vs_5_0, vShader()));
        SetHullShader(NULL);
        SetDomainShader(NULL);
        SetGeometryShader(NULL);
        SetPixelShader(CompileShader(ps_5_0, pShader()));
    }
}