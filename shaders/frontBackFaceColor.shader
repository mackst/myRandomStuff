Shader "Custom/frontBackFaceColor" {
    Properties {
        _frontColor ("Front Color", Color) = (1.0, 0., 0., 1.0)
        _backColor ("Back Color", Color) = (0.0, 0., 1., 1.0)
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
            
            // input from application
            struct APPDATA
            {
                float4 position : POSITION;
            };
            
            // output to fragment shader
            struct SHADERDATA
            {
                float4 position : SV_POSITION;
            };
            
            // vertex shader function
            SHADERDATA vert(APPDATA IN)
            {
                SHADERDATA OUT;
                OUT.position = mul(UNITY_MATRIX_MVP, IN.position);
                return OUT;
            }
            
            // fragment shader 
            float4 frag(SHADERDATA IN, bool frontFace : SV_IsFrontFace) : COLOR
            {
                float4 outColor;
                
                if (frontFace)
                    outColor = _frontColor;
                else
                    outColor = _backColor;
                
                return outColor;
            }

            ENDCG
        }
    } 
    FallBack "Diffuse"
}
