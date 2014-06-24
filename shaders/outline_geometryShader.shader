Shader "Custom/outline_geometryShader" {
    Properties 
    {
        _color ("Color", Color) = (.5, .5, .5, 1.0)
    }
    SubShader 
    {
        Pass 
        {
            CGPROGRAM
            #pragma vertex vert
            #pragma fragment frag
            #pragma geometry geom
            
            uniform float4 _color;
            
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
                OUT.position = mul(UNITY_MATRIX_MV, IN.position);
                return OUT;
            }
            
            // geometry shader
            [maxvertexcount(32)]
            void geom(triangleadj SHADERDATA IN[6], inout LineStream<SHADERDATA> lineStream)
			{
			    SHADERDATA OUT;
			    
			    float3 V0 = IN[0].position.xyz;
			    float3 V1 = IN[1].position.xyz;
			    float3 V2 = IN[2].position.xyz;
			    float3 V3 = IN[3].position.xyz;
			    float3 V4 = IN[4].position.xyz;
			    float3 V5 = IN[5].position.xyz;
			    
			    float3 N042 = cross(V4 - V0, V2 - V0);
			    float3 N021 = cross(V2 - V0, V1 - V0);
			    float3 N243 = cross(V4 - V2, V3 - V2);
			    float3 N405 = cross(V0 - V4, V5 - V4);
			    
			    // rashly assume all 4 normals are really meant to be
			    // within 90 degrees of each other
			    if (dot(N042, N021) < 0.)
			        N021 = -N021;
			    
			    if (dot(N042, N243) < 0.)
			        N243 = -N243;
			        
			    if (dot(N042, N405) < 0.)
			        N405 = -N405;
			        
			    // look for a silhouette edge between triangles 042 and 021
			    if (N042.z * N021.z < 0.)
			    {
			        OUT.position = mul(float4(V0, 1.0), UNITY_MATRIX_P);
			        lineStream.Append(OUT);
			        
			        OUT.position = mul(float4(V2, 1.0), UNITY_MATRIX_P);
			        lineStream.Append(OUT);
			        
			        lineStream.RestartStrip();
			    }
			    
			    // look for a silhouette edge between triangles 042 and 243
			    if (N042.z * N243.z < 0.)
			    {
			        OUT.position = mul(float4(V2, 1.0), UNITY_MATRIX_P);
			        lineStream.Append(OUT);
			        
			        OUT.position = mul(float4(V4, 1.0), UNITY_MATRIX_P);
			        lineStream.Append(OUT);
			        
			        lineStream.RestartStrip();
			    }
			    
			    // look for a silhouette edge between triangles 042 and 405
			    if (N042.z * N405.z < 0.)
			    {
			        OUT.position = mul(float4(V4, 1.0), UNITY_MATRIX_P);
			        lineStream.Append(OUT);
			        
			        OUT.position = mul(float4(V0, 1.0), UNITY_MATRIX_P);
			        lineStream.Append(OUT);
			        
			        lineStream.RestartStrip();
			    }
			}
			
			// fragment shader 
            float4 frag(SHADERDATA IN) : COLOR
            {
                return _color;
            }
            
            ENDCG
        }
    } 
}
