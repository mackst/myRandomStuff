// --------------------------------------- Per Object -----------------------------------------
cbuffer UpdatePerObject : register(b1)
{
    float4x4 worldIT : WorldInverseTranspose < string UIWidget = "None"; >;

    float4x4 wvp : WorldViewProjection < string UIWidget = "None"; >;

};

// --------------------------------------- Attributes -----------------------------------------
cbuffer UpdateAttributes : register(b2)
{
    float3 ambientColor
    <
        string UIName = "ambientColor";
        string UIWidget = "ColorPicker";
    > = {0.317464,0.317464,0.317464};

    float3 diffuseColor
    <
        string UIName = "diffuseColor";
        string UIWidget = "ColorPicker";
    > = {1.0,1.0,1.0};

};

// ----------------------------------- Lights --------------------------------------
cbuffer UpdateLights : register(b3)
{
    float3 Light1Dir : DIRECTION
    <
        string UIName =  "Light 1 Direction";
        string Space = "World";
        string Object =  "Light 1";
    > = {0.0, -1.0, 0.0};

};

// ---------------------------------------- Textures -----------------------------------------
Texture2D diffuseTexture
<
    string ResourceName = "";
    string UIName = "diffuseTexture";
    string ResourceType = "2D";
    string UIWidget = "FilePicker";
>;

SamplerState SamplerDiffuse
{
    Filter = MIN_MAG_MIP_LINEAR;
    AddressU = WRAP;
    AddressV = WRAP;
    AddressW = WRAP;
};


// -------------------------------------- APP and DATA  --------------------------------------
struct APPDATA
{
    float3 Position : POSITION;
    float3 Normal : NORMAL;
    float2 map1 : TEXCOORD0;
};

struct SHADERDATA
{
    float3 worldNormal : TEXCOORD0;
    float2 uv : TEXCOORD1;
    float4 position : SV_Position;
};

// -------------------------------------- ShaderVertex --------------------------------------
SHADERDATA ShaderVertex(APPDATA IN)
{
    SHADERDATA OUT;

    float3 normal = mul(IN.Normal, worldIT);
    OUT.worldNormal = normal;
    OUT.uv = IN.map1;
    float4 position = mul(float4(IN.Position, 1), wvp);
    OUT.position = position;

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

    float3 lightDir = normalize(-(Light1Dir));
    float lambert = saturate(dot(lightDir, normalize(IN.worldNormal)));
    float4 diffuseMap = diffuseTexture.Sample(SamplerDiffuse, float2(IN.uv.x, 1-IN.uv.y));
    float3 color = ((lambert + ambientColor.xyz) * (diffuseColor.xyz * diffuseMap.xyz));
    OUT.Color = float4(color.x, color.y, color.z, 1.0);

    return OUT;
}

// -------------------------------------- technique sample ---------------------------------------
technique11 sample
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

