Shader "Custom/discardShader" {
    Properties {
        _frontColor ("Front Color", Color) = (1.0, 0., 0., 1.0)
        _backColor ("Back Color", Color) = (0.0, 0., 1., 1.0)
        _discardU ("Discard U", Range(0.0, 1.0)) = .5
        _discardV ("Discard V", Range(0.0, 1.0)) = .5
    }
    SubShader {
        Pass {
            // set culling mode
            Cull Off
            
            CGPROGRAM
            #pragma vertex vert
            #pragma fragment frag
            
            uniform float4 _frontColor;
            uniform float4 _backColor;
            uniform float _discardU;
            uniform float _discardV;
            
            // input from application
            struct APPDATA
            {
                float4 position : POSITION;
                float2 uv : TEXCOORD0;
            };
            
            // output to fragment shader
            struct SHADERDATA
            {
                float4 position : SV_POSITION;
                float2 uv : TEXCOORD0;
            };
            
            // vertex shader function
            SHADERDATA vert(APPDATA IN)
            {
                SHADERDATA OUT;
                OUT.uv = IN.uv;
                OUT.position = mul(UNITY_MATRIX_MVP, IN.position);
                return OUT;
            }
            
            // fragment shader 
            float4 frag(SHADERDATA IN, bool frontFace : SV_IsFrontFace) : COLOR
            {
                float4 outColor;
                
                if (all(IN.uv < float2(_discardU, _discardV)))
                    discard;
                else
                {
                    if (frontFace)
                        outColor = _frontColor;
                    else
                        outColor = _backColor;
                }
                
                return outColor;
            }

            ENDCG
        }
    } 
}
