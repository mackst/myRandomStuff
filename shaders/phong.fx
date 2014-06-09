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
    > = {0.15,0.15,0.15};

    float3 diffuseColor
    <
        string UIName = "diffuseColor";
        string UIWidget = "ColorPicker";
    > = {0.7,0.7,0.7};

    float fresnelPower
    <
        float UIMin = 0.0;
        float UISoftMin = 0.0;
        float UIMax = 99.0;
        float UISoftMax = 99.0;
        float UIStep = 1.0;
        string UIName = "fresnelPower";
        string UIWidget = "Slider";
    > = 3.0;

    float specularPower
    <
        float UIMin = 0.0;
        float UISoftMin = 0.0;
        float UIMax = 99.0;
        float UISoftMax = 99.0;
        float UIStep = 0.01;
        string UIName = "specularPower";
        string UIWidget = "Slider";
    > = 30.0;

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

// -------------------------------------- APP and DATA  --------------------------------------
struct APPDATA
{
    float3 Position : POSITION;
    float3 Normal : NORMAL;
};

struct SHADERDATA
{
    float3 worldNormal : TEXCOORD0;
    float3 eyeVector : TEXCOORD1;
    float4 Position : SV_Position;
};

// -------------------------------------- ShaderVertex --------------------------------------
SHADERDATA ShaderVertex(APPDATA IN)
{
    SHADERDATA OUT;

    float3 worldNormal = mul(IN.Normal, worldIT);
    OUT.worldNormal = worldNormal;
    float3 CameraPosition = viewI[3].xyz;
    float3 worldSpacePos = mul(world, IN.Position);
    float3 eyeVector = (CameraPosition - worldSpacePos);
    OUT.eyeVector = eyeVector;
    float4 position = mul(float4(IN.Position, 1), wvp);
    OUT.Position = position;

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
    float3 worldNormal = normalize(IN.worldNormal);
    float lambert = saturate(dot(lightDir, worldNormal));
    
    float3 eyeVector = normalize(IN.eyeVector);
    float fresne = pow((1.0 - saturate(dot(eyeVector, worldNormal))), fresnelPower) * lambert;
    
    float3 reflectionVector = reflect(eyeVector, worldNormal);
    float specular = pow(saturate(dot(-(reflectionVector), lightDir)), specularPower);
    float3 color = (lambert + ambientColor.xyz) * diffuseColor.xyz + fresne + specular;
    float4 outColor = float4(color.x, color.y, color.z, 1.0);
    OUT.Color = outColor;

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

