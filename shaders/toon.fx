// ----------------------------------- Per Frame --------------------------------------
cbuffer UpdatePerFrame : register(b0)
{
    float4x4 viewI : ViewInverse < string UIWidget = "None"; >;

};

// --------------------------------------- Per Object -----------------------------------------
cbuffer UpdatePerObject : register(b1)
{
    float4x4 worldIT : WorldInverseTranspose < string UIWidget = "None"; >;

    float4x4 world : World < string UIWidget = "None"; >;

    float4x4 wvp : WorldViewProjection < string UIWidget = "None"; >;

};


// --------------------------------------- Attributes -----------------------------------------
cbuffer UpdateAttributes : register(b2)
{
    float3 ambientColor
    <
        string UIName = "ambientColor";
        string UIWidget = "ColorPicker";
    > = {0.5,0.5,0.5};

    float3 diffuseColor
    <
        string UIName = "diffuseColor";
        string UIWidget = "ColorPicker";
    > = {.8,.8,.8};

    float3 specColor
    <
        string UIName = "Specular Color";
        string UIWidget = "ColorPicker";
    > = {1.0,1.0,1.0};

    float diffuseThreshold
    <
        string UIWidget = "Slider";
        float UIMin = -1.0;
        float UIMax = 1.0;
        float UIStep = 0.001;
        string UIName = "Lighting Threshold";
    > = .1;
    
    float diffusion
    <
        string UIWidget = "Slider";
        float UIMin = -1.0;
        float UIMax = 1.0;
        float UIStep = 0.001;
        string UIName = "Diffusion";
    > = .5;
    
    float shininess
    <
        string UIWidget = "Slider";
        float UIMin = 0.0;
        float UIMax = 1.0;
        float UIStep = 0.001;
        string UIName = "Shininess";
    > = .6;
    
    float specDiffusion
    <
        string UIWidget = "Slider";
        float UIMin = 0.0;
        float UIMax = 1.0;
        float UIStep = .001;
        string UIName = "Specular Diffusion";
    > = .0;s
};

// ----------------------------------- Lights --------------------------------------
cbuffer UpdateLights : register(b3)
{
    float3 Light1Dir : Direction
    <
        string UIName =  "Light 1 Direction";
        string Space = "World";
        string Object =  "Light 1";
    > = {0.0, -1.0, 0.0};
    
    float Light1Intensity : LightIntensity
    <
        string UIName =  "Light 1 Position";
        string Object =  "Light 1";
    > = {1.0};
};

// -------------------------------------- APP and DATA  --------------------------------------
struct APPDATA
{
    float3 Position : POSITION;
    float3 Normal : NORMAL;
};

struct SHADERDATA
{
    float4 Position : SV_Position;
    float3 worldNormal : TEXCOORD0;
    float3 viewDir : TEXCOORD1;
};

// -------------------------------------- ShaderVertex --------------------------------------
SHADERDATA ShaderVertex(APPDATA IN)
{
    SHADERDATA OUT;
    
    OUT.worldNormal = mul(IN.Normal, worldIT);
    OUT.Position = mul(float4(IN.Position, 1), wvp);
    OUT.viewDir = normalize(viewI[3].xyz - mul(IN.Position, world));
    
    return OUT;
}

// -------------------------------------- ShaderPixel --------------------------------------
struct PIXELDATA
{
    float4 Color : SV_Target;
};

PIXELDATA ShaderPixel(SHADERDATA IN)
{
    PIXELDATA OUT;

    float dotL = saturate(dot(IN.worldNormal, Light1Dir));
    float diffuseCutoff = saturate((max(diffuseThreshold, dotL) - diffuseThreshold) * pow((2 - diffusion), 10));
    float specularCutoff = saturate((max(shininess, dot(reflect(-Light1Dir, IN.worldNormal), IN.viewDir)) - shininess) * pow((2 - specDiffusion), 10));
    
    float3 ambientLight = (1 - diffuseCutoff) * ambientColor;
    float3 diffuseReflection = (1 - specularCutoff) * diffuseColor * diffuseCutoff;
    float3 specularReflection = specColor * specularCutoff;
    
    OUT.Color.rgb = ambientLight + diffuseReflection + specularReflection;
    OUT.Color.a = 1.0;
    
    return OUT;
}

// -------------------------------------- technique sample ---------------------------------------
technique11 sample
<
    //int isTransparent = 3;
>
{
    pass P0
    <
        string drawContext = "colorPass";
    >
    {
        SetVertexShader(CompileShader(vs_5_0, ShaderVertex()));
        SetPixelShader(CompileShader(ps_5_0, ShaderPixel()));
        SetHullShader(NULL);
        SetDomainShader(NULL);
        SetGeometryShader(NULL);
    }

}

