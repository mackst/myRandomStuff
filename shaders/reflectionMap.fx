// ----------------------------------- Per Frame --------------------------------------
cbuffer UpdatePerFrame : register(b0)
{
    float4x4 viewI : ViewInverse < string UIWidget = "None"; >;

};

// --------------------------------------- Per Object -----------------------------------------
cbuffer UpdatePerObject : register(b1)
{
    float4x4 world : World < string UIWidget = "None"; >;

    float4x4 worldIT : WorldInverseTranspose < string UIWidget = "None"; >;

    float4x4 wvp : WorldViewProjection < string UIWidget = "None"; >;

};

// ---------------------------------------- Textures -----------------------------------------
TextureCube reflectionTex
<
    string ResourceName = "";
    string UIName = "reflection Texeture";
    string ResourceType = "Cube";
    string UIWidget = "FilePicker";
>;

SamplerState MMMLWWWSampler
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
};

struct SHADERDATA
{
    float3 eyeVector : TEXCOORD0;
    float3 normal : NORMAL;
    float4 position : SV_Position;
};

// -------------------------------------- ShaderVertex --------------------------------------
SHADERDATA ShaderVertex(APPDATA IN)
{
    SHADERDATA OUT;

    float3 CameraPosition = viewI[3].xyz;
    float3 worldPosition = mul(IN.Position, world);
    OUT.eyeVector = CameraPosition - worldPosition;
    OUT.normal = mul(IN.Normal, worldIT);
    OUT.position = mul(float4(IN.Position, 1), wvp);

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

    float3 reflectVector = reflect(IN.eyeVector, IN.normal);
    OUT.Color = reflectionTex.Sample(MMMLWWWSampler, reflectVector);

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

