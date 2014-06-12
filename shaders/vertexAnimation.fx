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


// using http://adrianboeing.blogspot.com/2011/02/ripple-effect-in-webgl.html
// to make ripple effect

#define PI 3.1415926

float4x4 world                 : World                   < string UIWidget = "None"; >;
float4x4 wvp                   : WorldViewProjection     < string UIWidget = "None"; >;
float4x4 worldInverseTranspose : WorldInverseTranspose   < string UIWidget = "None"; >;

// time from maya
float time : Time < string UIWidget = "None"; >;

// render state
RasterizerState wireframeState
{
    CullMode = None;
    FillMode = WIREFRAME;
};

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

// ripple control attributes
float Amplitude
<
    string UIGroup = "Ripple";
    string UIName = "Amplitude";
    int UIOrder = 11;
    float UIMin = 0.0;
    float UISoftMax = 1.0;
    float UIMax = 10.0;
    float UIStep = 0.1;
> = 0.125f;

float Frequency
<
    string UIGroup = "Ripple";
    string UIName = "Frequency";
    int UIOrder = 12;
    float UIMin = 0.1;
    float UISoftMax = 1.0;
    float UIMax = 10.0;
    float UIStep = 0.1;
> = .5f;



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
    float r = length(IN.position.xz);
    float y = Amplitude * sin(PI * r * Frequency * time) / r;
    OUT.position = mul(float4(IN.position.x, y, IN.position.z, 1.), wvp);
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
    
    float lambert = saturate(dot(lightDir, worldNormal));
    
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
        SetRasterizerState(wireframeState);
    }
}