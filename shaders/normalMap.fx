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

Texture2D normalTexture
<
    string ResourceName = "";
    string UIName = "normalTexture";
    string ResourceType = "2D";
    string UIWidget = "FilePicker";
>;

SamplerState textureSampler
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
    float3 Tangent : TANGENT;
    float3 BiNormal : BINORMAL;
    float2 map1 : TEXCOORD0;
};

struct SHADERDATA
{
    float2 uv : TEXCOORD0;
    float3 worldNormal : TEXCOORD1;
    float3 tangent : TEXCOORD2;
    float3 binormal : TEXCOORD3;
    float4 position : SV_Position;
};

// -------------------------------------- ShaderVertex --------------------------------------
SHADERDATA ShaderVertex(APPDATA IN)
{
    SHADERDATA OUT;

    OUT.worldNormal = mul(IN.Normal, worldIT);
    OUT.uv = IN.map1;
    OUT.tangent = IN.Tangent;
    OUT.binormal = IN.BiNormal;
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
    float3 worldNormal = normalTexture.Sample(textureSampler, float2(IN.uv.x, 1-IN.uv.y)).rgb * 2.0 - 1.0;
    worldNormal = ((worldNormal.x * IN.tangent) + (worldNormal.y * IN.binormal) + (worldNormal.z * IN.worldNormal));
    float lambert = saturate(dot(lightDir, normalize(IN.worldNormal)));
    float4 diffuseMap = diffuseTexture.Sample(textureSampler, float2(IN.uv.x, 1-IN.uv.y));
    float3 color = ((lambert + ambientColor.xyz) * (diffuseColor.xyz * diffuseMap.xyz));
    OUT.Color = float4(color.x, color.y, color.z, 1.0);
    //OUT.Color = float4(worldNormal, 1.0);

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

