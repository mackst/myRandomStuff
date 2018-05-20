using System;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Collections.Generic;
using System.Runtime.InteropServices;

using Autodesk.Maya.OpenMaya;
using Autodesk.Maya.OpenMayaAnim;

using Vulkan;


//-----------------------------------------------------------------------
// time spaced: 108.9517195 seconds. // 
// 结果: yTwistCSharp1 // 
// time spaced: 139.511697 seconds. // 
//-----------------------------------------------------------------------




[assembly: MPxNodeClass(typeof(MayaNetPlugin.yTwistNode), "yTwistCSharp", 0x0008106d,
    NodeType = MPxNode.NodeType.kDeformerNode)]

namespace MayaNetPlugin
{
    [MPxNodeAffects("angle", "outputGeom")]
    class yTwistNode : MPxGeometryFilter, IMPxNode
    {
        [MPxNodeNumeric("fa", "angle", MFnNumericData.Type.kDouble, Keyable = true)]
        public static MObject angle = null;

        public yTwistNode()
        {
        }

        override public void deform(MDataBlock block, MItGeometry iter, MMatrix m, uint multiIndex)
        {
            MDataHandle angleData = block.inputValue(angle);
            MDataHandle envData = block.inputValue(envelope);
            double magnitude = angleData.asDouble;

            float env = envData.asFloat;

            var startTime = DateTime.Now;

            var poses = new MPointArray();
            iter.allPositions(poses);

            //var newPos = VulankCompute.ComputeData(poses, (float)magnitude, env);
            VulankCompute.ComputeData(poses, (float)magnitude, env);

            iter.setAllPositions(poses);

            var timeSpand = DateTime.Now - startTime;
            MGlobal.displayInfo(string.Format("---------- total time : {0}", timeSpand.TotalSeconds));
            //for (; !iter.isDone; iter.next())
            //{
                //MPoint pt = iter.position();

                //// do the twist
                ////

                //double ff = magnitude * pt.y * env;
                //if (ff != 0.0)
                //{
                //    double cct = Math.Cos(ff);
                //    double cst = Math.Sin(ff);
                //    double tt = pt.x * cct - pt.z * cst;
                //    pt.z = pt.x * cst + pt.z * cct;
                //    pt.x = tt; ;
                //}

                //iter.setPosition(pt);
            //}
        }
    }

    //struct UBO
    //{
    //    public float numvert;
    //    public float angle;
    //    public float envolope;
    //}


    class VulankCompute
    {

        static public uint FindBestComputeQueue(PhysicalDevice physicalDevice)
        {
            uint i = 0;
            foreach(var queueFamily in physicalDevice.GetQueueFamilyProperties())
            {
                var maskedFlages = (QueueFlags.Transfer | QueueFlags.Compute) & queueFamily.QueueFlags;

                if (maskedFlages == QueueFlags.Compute)
                {
                    return i;
                }
                i++;
            }

            return (~0U);
        }

        static public MPointArray ComputeData(MPointArray inPos, float angle, float envolope)
        {
            var memorySize = inPos.Count * 4 * sizeof(float);
            float[] ubo = { inPos.Count, angle, envolope };

            // pos to float[]
            float[] allPos = new float[inPos.Count * 4];
            var i = 0;
            foreach (var point in inPos)
            {
                allPos[i * 4 + 0] = (float)point.x;
                allPos[i * 4 + 1] = (float)point.y;
                allPos[i * 4 + 2] = (float)point.z;
                allPos[i * 4 + 3] = (float)point.w;
                i++;
            }

            var instance = new Instance(new InstanceCreateInfo {
                ApplicationInfo = new ApplicationInfo {
                    ApplicationName = "CSharp Vulkan",
                    ApplicationVersion = Vulkan.Version.Make(1, 0, 0),
                    ApiVersion = Vulkan.Version.Make(1, 0, 0),
                    EngineName = "CSharp Engine",
                    EngineVersion = Vulkan.Version.Make(1, 0, 0)
                },
                //EnabledExtensionCount = 0,
                //EnabledLayerCount = 0
                EnabledExtensionNames = new string[] { "VK_EXT_debug_report" },
                EnabledLayerNames = new string[] { "VK_LAYER_LUNARG_standard_validation" }
            });

            var debugCallback = new Instance.DebugReportCallback(DebugReportCallback);
            instance.EnableDebug(debugCallback, DebugReportFlagsExt.Warning | DebugReportFlagsExt.Error);

            PhysicalDevice physicalDevice = instance.EnumeratePhysicalDevices()[0];
           
            var queueFamilyIndex = FindBestComputeQueue(physicalDevice);

            DeviceQueueCreateInfo[] deviceQueueCreateInfo = 
            {
                new DeviceQueueCreateInfo
                {
                    QueueFamilyIndex = queueFamilyIndex,
                    QueueCount = 1,
                    QueuePriorities = new float[] { 1.0f }
                }
            };

            var deviceCreateInfo = new DeviceCreateInfo
            {
                QueueCreateInfos = deviceQueueCreateInfo,
                EnabledFeatures = new PhysicalDeviceFeatures(),
                EnabledExtensionCount = 0,
                //EnabledLayerCount = 0
                //EnabledExtensionNames = new string[] { "VK_EXT_debug_report" },
                EnabledLayerNames = new string[] { "VK_LAYER_LUNARG_standard_validation" }
            };

            var device = physicalDevice.CreateDevice(deviceCreateInfo);

            //var memProperties = physicalDevice.GetMemoryProperties();

            var bufferCreateInfo = new BufferCreateInfo
            {
                Size = memorySize,
                Usage = BufferUsageFlags.StorageBuffer,
                SharingMode = SharingMode.Exclusive,
                QueueFamilyIndices = new uint[] { queueFamilyIndex }
            };

            var inBuffer = device.CreateBuffer(bufferCreateInfo);
            var outBuffer = device.CreateBuffer(bufferCreateInfo);

            var memRequirements = device.GetBufferMemoryRequirements(inBuffer);

            uint memIndex = FindMemoryType(physicalDevice, memRequirements.MemoryTypeBits, MemoryPropertyFlags.HostVisible | MemoryPropertyFlags.HostCoherent);

            var memoryAllocatInfo = new MemoryAllocateInfo
            {
                AllocationSize = memRequirements.Size,
                MemoryTypeIndex = memIndex
            };

            var memory = device.AllocateMemory(memoryAllocatInfo);

            var dataPtr = device.MapMemory(memory, 0, memorySize);

            Marshal.Copy(allPos, 0, dataPtr, allPos.Length);

            device.UnmapMemory(memory);

            memRequirements = device.GetBufferMemoryRequirements(outBuffer);
            memoryAllocatInfo.MemoryTypeIndex = FindMemoryType(physicalDevice, memRequirements.MemoryTypeBits, MemoryPropertyFlags.HostVisible | MemoryPropertyFlags.HostCoherent);
            var outMemory = device.AllocateMemory(memoryAllocatInfo);

            device.BindBufferMemory(inBuffer, memory, 0);
            device.BindBufferMemory(outBuffer, outMemory, 0);

            //var uboSize = Marshal.SizeOf(ubo);
            var uboSize = 3 * sizeof(float);
            var uboBufferCreateInfo = new BufferCreateInfo
            {
                Size = uboSize,
                Usage = BufferUsageFlags.UniformBuffer,
                SharingMode = SharingMode.Exclusive,
                QueueFamilyIndices = new uint[] { queueFamilyIndex }
            };

            var uboBuffer = device.CreateBuffer(uboBufferCreateInfo);
            memRequirements = device.GetBufferMemoryRequirements(uboBuffer);

            var uboMemoryAllocInfo = new MemoryAllocateInfo
            {
                AllocationSize = memRequirements.Size,
                MemoryTypeIndex = FindMemoryType(physicalDevice, memRequirements.MemoryTypeBits, MemoryPropertyFlags.HostVisible | MemoryPropertyFlags.HostCoherent)
            };

            var uboMemory = device.AllocateMemory(uboMemoryAllocInfo);
            var uboPtr = device.MapMemory(uboMemory, 0, uboSize);
            Marshal.Copy(ubo, 0, uboPtr, ubo.Length);
            device.UnmapMemory(uboMemory);

            device.BindBufferMemory(uboBuffer, uboMemory, 0);

            //string textureName = string.Format("{0}.comp.spv", typeof(VulankCompute).Namespace);
            //Stream stream = typeof(VulankCompute).GetTypeInfo().Assembly.GetManifestResourceStream(textureName);
            string shaderFile = @"E:\coding\CShape\yTwistCSharpVulkan\comp.spv";
            Stream stream = File.Open(shaderFile, FileMode.Open);
            byte[] shaderCode = new byte[stream.Length];
            stream.Read(shaderCode, 0, (int)stream.Length);
            stream.Close();
            stream.Dispose();
            var shaderModule = device.CreateShaderModule(shaderCode);

            DescriptorSetLayoutBinding[] descriptorSetLayoutBindings =
            {
                new DescriptorSetLayoutBinding
                {
                    Binding = 0,
                    DescriptorType = DescriptorType.StorageBuffer,
                    DescriptorCount = 1,
                    StageFlags = ShaderStageFlags.Compute
                },

                new DescriptorSetLayoutBinding
                {
                    Binding = 1,
                    DescriptorType = DescriptorType.StorageBuffer,
                    DescriptorCount = 1,
                    StageFlags = ShaderStageFlags.Compute
                },

                new DescriptorSetLayoutBinding
                {
                    Binding = 2,
                    DescriptorType = DescriptorType.UniformBuffer,
                    DescriptorCount = 1,
                    StageFlags = ShaderStageFlags.Compute
                }
            };

            var descriporSetLayoutCreateinfo = new DescriptorSetLayoutCreateInfo
            {
                Bindings = descriptorSetLayoutBindings
            };

            var descriptorSetLayout = device.CreateDescriptorSetLayout(descriporSetLayoutCreateinfo);

            var descriptorPool = device.CreateDescriptorPool(new DescriptorPoolCreateInfo
            {
                MaxSets = 1,
                PoolSizes = new DescriptorPoolSize[]
                {
                    new DescriptorPoolSize
                    {
                        DescriptorCount = 3
                    }
                }
            });

            var descriptorSet = device.AllocateDescriptorSets(new DescriptorSetAllocateInfo
            {
                DescriptorPool = descriptorPool,
                SetLayouts = new DescriptorSetLayout[] { descriptorSetLayout }
            })[0];

            var inBufferInfo = new DescriptorBufferInfo
            {
                Buffer = inBuffer,
                Offset = 0,
                Range = memorySize
            };

            var outBufferInfo = new DescriptorBufferInfo
            {
                Buffer = outBuffer,
                Offset = 0,
                Range = memorySize
            };

            var uboBufferInfo = new DescriptorBufferInfo
            {
                Buffer = uboBuffer,
                Offset = 0,
                Range = uboSize
            };

            WriteDescriptorSet[] writeDescriptorSets =
            {
                new WriteDescriptorSet
                {
                    DstSet = descriptorSet,
                    DstBinding = 0,
                    DstArrayElement = 0,
                    DescriptorCount = 1,
                    DescriptorType = DescriptorType.StorageBuffer,
                    BufferInfo = new DescriptorBufferInfo[] { inBufferInfo }
                },

                new WriteDescriptorSet
                {
                    DstSet = descriptorSet,
                    DstBinding = 1,
                    DstArrayElement = 0,
                    DescriptorCount = 1,
                    DescriptorType = DescriptorType.StorageBuffer,
                    BufferInfo = new DescriptorBufferInfo[] { outBufferInfo }
                },

                new WriteDescriptorSet
                {
                    DstSet = descriptorSet,
                    DstBinding = 2,
                    DstArrayElement = 0,
                    DescriptorCount = 1,
                    DescriptorType = DescriptorType.UniformBuffer,
                    BufferInfo = new DescriptorBufferInfo[] { uboBufferInfo }
                }
            };

            device.UpdateDescriptorSets(writeDescriptorSets, null);

            var pipelineLayout = device.CreatePipelineLayout(new PipelineLayoutCreateInfo
            {
                SetLayouts = new DescriptorSetLayout[] { descriptorSetLayout }
            });

            var shaderStage = new PipelineShaderStageCreateInfo
            {
                Stage = ShaderStageFlags.Compute,
                Module = shaderModule,
                Name = "main"
            };

            var pipeline = device.CreateComputePipelines(null, new ComputePipelineCreateInfo[]
            {
                new ComputePipelineCreateInfo
                {
                    Stage = shaderStage,
                    Layout = pipelineLayout
                }
            })[0];

            var commandPool = device.CreateCommandPool(new CommandPoolCreateInfo
            {
                QueueFamilyIndex = queueFamilyIndex
            });

            var cmdBuffer = device.AllocateCommandBuffers(new CommandBufferAllocateInfo
            {
                CommandPool = commandPool,
                CommandBufferCount = 1,
                Level = CommandBufferLevel.Primary
            })[0];

            cmdBuffer.Begin(new CommandBufferBeginInfo
            {
                Flags = CommandBufferUsageFlags.OneTimeSubmit
            });

            cmdBuffer.CmdBindPipeline(PipelineBindPoint.Compute, pipeline);

            cmdBuffer.CmdBindDescriptorSet(PipelineBindPoint.Compute, pipelineLayout, 0, descriptorSet, null);

            cmdBuffer.CmdDispatch((uint)inPos.Count, 1, 1);

            cmdBuffer.End();

            var queue = device.GetQueue(queueFamilyIndex, 0);
            //var fence = device.CreateFence(new FenceCreateInfo { Flags=0 });
            queue.Submit(new SubmitInfo
            {
                WaitSemaphoreCount = 0,
                CommandBuffers = new CommandBuffer[] { cmdBuffer },
            });
            queue.WaitIdle();
            //device.WaitForFence(fence, true, UInt64.MaxValue);

            var newDataPtr = device.MapMemory(outMemory, 0, memorySize);
            Marshal.Copy(newDataPtr, allPos, 0, allPos.Length);
            device.UnmapMemory(outMemory);

            var j = 0;
            foreach(var p in inPos)
            {
                p.x = allPos[j * 4 + 0];
                p.y = allPos[j * 4 + 1];
                p.z = allPos[j * 4 + 2];
                p.w = allPos[j * 4 + 3];
                j++;
            }

            //device.DestroyFence(fence);
            device.DestroyShaderModule(shaderModule);
            device.DestroyCommandPool(commandPool);
            device.DestroyDescriptorSetLayout(descriptorSetLayout);
            device.DestroyDescriptorPool(descriptorPool);
            device.DestroyPipelineLayout(pipelineLayout);
            device.DestroyPipeline(pipeline);
            device.DestroyBuffer(inBuffer);
            device.DestroyBuffer(outBuffer);
            device.DestroyBuffer(uboBuffer);
            device.FreeMemory(memory);
            device.FreeMemory(outMemory);
            device.FreeMemory(uboMemory);
            device.Destroy();
            
            //instance.Destroy();

            return inPos;
        }

        static uint FindMemoryType(PhysicalDevice physicalDevice, uint typeFilter, MemoryPropertyFlags propertyFlags)
        {
            var memProperties = physicalDevice.GetMemoryProperties();

            uint i = 0;
            foreach (var memType in memProperties.MemoryTypes)
            {
                if ((((typeFilter >> (int)i) & 1) == 1) && ((memType.PropertyFlags & propertyFlags) == propertyFlags))
                    return i;
                i++;
            }

            MGlobal.displayError("failed to find memory type");
            throw new Exception("failed to find memory type");
        }

        static public Bool32 DebugReportCallback(DebugReportFlagsExt flags, DebugReportObjectTypeExt objectType, ulong objectHandle, IntPtr location, int messageCode, IntPtr layerPrefix, IntPtr message, IntPtr userData)
        {
            string layerString = Marshal.PtrToStringAnsi(layerPrefix);
            string messageString = Marshal.PtrToStringAnsi(message);

            MGlobal.displayError(string.Format("DebugReport layer: {0} message: {1}", layerString, messageString));
            //Console.WriteLine("DebugReport layer: {0} message: {1}", layerString, messageString);

            return false;
        }
    }

}
