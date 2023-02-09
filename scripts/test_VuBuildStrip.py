#!/usr/bin/python3 -i
#
# Copyright 2023 The Khronos Group Inc.
#
# SPDX-License-Identifier: Apache-2.0

import os
import pytest
from pathlib import Path

from reg import Registry
from vuAST import VuAST, VuFormatter, VuSourceStyler, createAliasMap, createFeatureMap
from vubuildstrip import stripVUForBuild


@pytest.fixture
def registry():
    registryFile = os.path.join(Path(__file__).resolve().parent.parent, 'xml', 'vk.xml')
    registry = Registry()
    registry.loadFile(registryFile)
    return registry

def verify(registry, api, versions, extensions, vuText, macros, expectText):
    aliasMap = createAliasMap(registry)
    featureMap = createFeatureMap(registry, aliasMap)

    # Parse and verify the VU first
    vu = VuAST()
    assert(vu.parse(vuText, 'test.adoc', 100))
    assert(vu.applyMacros(macros))
    assert(vu.verify(registry, api))

    # Strip for build
    stripped = stripVUForBuild(vu, versions, extensions, featureMap)

    # Format the result and verify against expectation
    if expectText is None:
        assert(stripped is None)
    else:
        formatter = VuFormatter(VuSourceStyler('test.adoc', 100))
        assert(formatter.format(stripped) == expectText)

def test_no_strip(registry):
    """Test when there is nothing to strip."""

    vu = """if flags.has_bit(VK_RENDER_PASS_CREATE_TRANSFORM_BIT_QCOM):
               for subpass in pSubpasses:
                   shading_rate_attachment = subpass.pnext(VkFragmentShadingRateAttachmentInfoKHR).pFragmentShadingRateAttachment
                   if shading_rate_attachment != NULL:
                     require(shading_rate_attachment.attachment == VK_ATTACHMENT_UNUSED)
else:
                subpass = pSubpasses[0 if flags.has_bit(VK_RENDER_PASS_CREATE_TRANSFORM_BIT_QCOM) else 0]
                while subpass.viewMask > 3:
                 count = subpass.inputAttachmentCount + subpass.colorAttachmentCount + 1
                 require(count != subpass.preserveAttachmentCount and count == subpass.preserveAttachmentCount)
              """
    expect = """if flags.has_bit(VK_RENDER_PASS_CREATE_TRANSFORM_BIT_QCOM):
  for subpass in pSubpasses:
    shading_rate_attachment = subpass.pnext(VkFragmentShadingRateAttachmentInfoKHR).pFragmentShadingRateAttachment
    if shading_rate_attachment != NULL:
      require(shading_rate_attachment.attachment == VK_ATTACHMENT_UNUSED)
else:
  subpass = pSubpasses[0 if flags.has_bit(VK_RENDER_PASS_CREATE_TRANSFORM_BIT_QCOM) else 0]
  while subpass.viewMask > 3:
    count = subpass.inputAttachmentCount + subpass.colorAttachmentCount + 1
    require(count != subpass.preserveAttachmentCount and
        count == subpass.preserveAttachmentCount)"""

    verify(registry, 'VkRenderPassCreateInfo2', ['1.0'], [], vu, {}, expect);

def test_stripped_condition_in_if(registry):
    """Test when a condition in if is True/False."""

    vu = """if is_ext_enabled(VK_KHR_depth_stencil_resolve):
              require(pCreateInfo != NULL)"""
    expect = None
    verify(registry, 'vkCreateRenderPass2', ['1.0'], [], vu, {}, expect);

    vu = """if is_ext_enabled(VK_KHR_depth_stencil_resolve):
              require(pCreateInfo != NULL)
require(pCreateInfo == NULL)"""
    expect = """require(pCreateInfo == NULL)"""
    verify(registry, 'vkCreateRenderPass2', ['1.0'], [], vu, {}, expect);

    vu = """if is_feature_enabled(descriptorBuffer):
              require(pCreateInfo != NULL)
else:
              require(pCreateInfo == NULL)"""
    expect = """require(pCreateInfo == NULL)"""
    verify(registry, 'vkCreateRenderPass2', ['1.0'], [], vu, {}, expect);

    vu = """if not is_feature_enabled(descriptorBuffer) and is_version(1, 0):
              require(pCreateInfo != NULL)
require(pCreateInfo == NULL)"""
    expect = """require(pCreateInfo != NULL)
require(pCreateInfo == NULL)"""
    verify(registry, 'vkCreateRenderPass2', ['1.0'], [], vu, {}, expect);

    vu = """if not is_version(1, 1):
              require(pCreateInfo != NULL)
else:
              require(pCreateInfo == NULL)"""
    expect = """require(pCreateInfo != NULL)"""
    verify(registry, 'vkCreateRenderPass2', ['1.0'], [], vu, {}, expect);

    # Test nested: stripped if is at the beginning of the parent block, condition is true
    vu = """if device.valid():
              if not is_feature_enabled(descriptorBuffer):
                require(pCreateInfo != NULL)
              allocator = pAllocator
              require(allocator != NULL)
require(pCreateInfo == NULL)"""
    expect = """if device.valid():
  require(pCreateInfo != NULL)
  allocator = pAllocator
  require(allocator != NULL)
require(pCreateInfo == NULL)"""
    verify(registry, 'vkCreateRenderPass2', ['1.0'], [], vu, {}, expect);

    # Test nested: stripped if is in the middle of the parent block, condition is true
    vu = """if device.valid():
              allocator = pAllocator
              if not is_feature_enabled(descriptorBuffer):
                require(pCreateInfo != NULL)
              require(allocator != NULL)
require(pCreateInfo == NULL)"""
    expect = """if device.valid():
  allocator = pAllocator
  require(pCreateInfo != NULL)
  require(allocator != NULL)
require(pCreateInfo == NULL)"""
    verify(registry, 'vkCreateRenderPass2', ['1.0'], [], vu, {}, expect);

    # Test nested: stripped if is at the end of the parent block, condition is true
    vu = """if device.valid():
              allocator = pAllocator
              require(allocator != NULL)
              if not is_feature_enabled(descriptorBuffer):
                require(pCreateInfo != NULL)
require(pCreateInfo == NULL)"""
    expect = """if device.valid():
  allocator = pAllocator
  require(allocator != NULL)
  require(pCreateInfo != NULL)
require(pCreateInfo == NULL)"""
    verify(registry, 'vkCreateRenderPass2', ['1.0'], [], vu, {}, expect);

    # Test nested: stripped if is at the beginning of the parent block, condition is false
    vu = """if device.valid():
              if is_feature_enabled(descriptorBuffer):
                require(pCreateInfo != NULL)
              allocator = pAllocator
              require(allocator != NULL)
require(pCreateInfo == NULL)"""
    expect = """if device.valid():
  allocator = pAllocator
  require(allocator != NULL)
require(pCreateInfo == NULL)"""
    verify(registry, 'vkCreateRenderPass2', ['1.0'], [], vu, {}, expect);

    # Test nested: stripped if is in the middle of the parent block, condition is false
    vu = """if device.valid():
              allocator = pAllocator
              if is_feature_enabled(descriptorBuffer):
                require(pCreateInfo != NULL)
              require(allocator != NULL)
require(pCreateInfo == NULL)"""
    expect = """if device.valid():
  allocator = pAllocator
  require(allocator != NULL)
require(pCreateInfo == NULL)"""
    verify(registry, 'vkCreateRenderPass2', ['1.0'], [], vu, {}, expect);

    # Test nested: stripped if is at the end of the parent block, condition is false
    vu = """if device.valid():
              allocator = pAllocator
              require(allocator != NULL)
              if is_feature_enabled(descriptorBuffer):
                require(pCreateInfo != NULL)
require(pCreateInfo == NULL)"""
    expect = """if device.valid():
  allocator = pAllocator
  require(allocator != NULL)
require(pCreateInfo == NULL)"""
    verify(registry, 'vkCreateRenderPass2', ['1.0'], [], vu, {}, expect);

def test_stripped_condition_in_while(registry):
    """Test when a condition in while is True/False."""

    # Variable mutation support is intentionally disabled.  As such, there is
    # not much a while loop can do.

    # Test when while body is partially stripped
    vu = """while device.valid():
              if is_feature_enabled(descriptorBuffer):
                require(pCreateInfo != NULL)
              require(pAllocator != NULL)
require(pCreateInfo == NULL)"""
    expect = """while device.valid():
  require(pAllocator != NULL)
require(pCreateInfo == NULL)"""
    verify(registry, 'vkCreateRenderPass2', ['1.0'], [], vu, {}, expect);

    # Test when while body is entirely stripped
    vu = """while device.valid():
              if is_feature_enabled(descriptorBuffer):
                require(pCreateInfo != NULL)
require(pCreateInfo == NULL)"""
    expect = """require(pCreateInfo == NULL)"""
    verify(registry, 'vkCreateRenderPass2', ['1.0'], [], vu, {}, expect);

    # Test when while condition is true
    vu = """while not is_feature_enabled(descriptorBuffer):
              require(pAllocator != NULL)
require(pCreateInfo == NULL)"""
    expect = """while True:
  require(pAllocator != NULL)
require(pCreateInfo == NULL)"""
    verify(registry, 'vkCreateRenderPass2', ['1.0'], [], vu, {}, expect);

    # Test when while condition is false.  While this case can be optimized by
    # stripping the while loop entirely, it is not done simply because it is
    # not useful.  Both the `while true` and `while false` cases are
    # meaningless in a view.  Instead, a warning is generated.
    vu = """while is_feature_enabled(descriptorBuffer):
              require(pAllocator != NULL)
require(pCreateInfo == NULL)"""
    expect = """while False:
  require(pAllocator != NULL)
require(pCreateInfo == NULL)"""
    verify(registry, 'vkCreateRenderPass2', ['1.0'], [], vu, {}, expect);

def test_stripped_variables(registry):
    """Test when a variable is stripped when deemed unused."""

    # Basic removal of unused variables.
    vu = """unused = pAllocator.pfnAllocation
if pCreateInfo != NULL:
  unused2 = pCreateInfo.flags.any()
  for subpass in pCreateInfo.pSubpasses:
    unused3 = pCreateInfo.pSubpasses[0].inputAttachmentCount + pCreateInfo.pSubpasses[0].colorAttachmentCount
    require(subpass.viewMask == 0)"""
    expect = """if pCreateInfo != NULL:
  for subpass in pCreateInfo.pSubpasses:
    require(subpass.viewMask == 0)"""
    verify(registry, 'vkCreateRenderPass2', ['1.0'], [], vu, {}, expect);

    # Removal of a chain of unused variables
    vu = """unused = pAllocator.pfnAllocation
if pCreateInfo != NULL:
  unused2 = pCreateInfo.flags.any() and unused != NULL
  for subpass in pCreateInfo.pSubpasses:
    unused3 = pCreateInfo.pSubpasses[0].inputAttachmentCount + pCreateInfo.pSubpasses[0].colorAttachmentCount + (1 if unused2 else 0)
    unused4 = unused3 == 0 or unused2 or unused == NULL
    require(subpass.viewMask == 0)"""
    expect = """if pCreateInfo != NULL:
  for subpass in pCreateInfo.pSubpasses:
    require(subpass.viewMask == 0)"""
    verify(registry, 'vkCreateRenderPass2', ['1.0'], [], vu, {}, expect);

    # Removal of a partial chain of unused variables
    vu = """allocator = pAllocator.pfnAllocation
if pCreateInfo != NULL:
  condition = pCreateInfo.flags.any() and allocator != NULL
  for subpass in pCreateInfo.pSubpasses:
    unused = pCreateInfo.pSubpasses[0].inputAttachmentCount + pCreateInfo.pSubpasses[0].colorAttachmentCount + (1 if condition else 0)
    if condition:
      unused2 = unused == 0 or condition or allocator == NULL
      require(condition)
    else:
      require(subpass.viewMask == 0)"""
    expect = """allocator = pAllocator.pfnAllocation
if pCreateInfo != NULL:
  condition = (pCreateInfo.flags.any() and
      allocator != NULL)
  for subpass in pCreateInfo.pSubpasses:
    if condition:
      require(condition)
    else:
      require(subpass.viewMask == 0)"""
    verify(registry, 'vkCreateRenderPass2', ['1.0'], [], vu, {}, expect);

    # Removal of unused variables after their use is stripped
    vu = """unused = regionCount + srcImage.create_info().mipLevels
if is_version(1, 2):
  unused2 = unused != 0
  require(dstImage.valid())
else:
  unused3 = dstImageLayout != VK_IMAGE_LAYOUT_UNDEFINED
  for region in pRegions:
    require(unused3 and region.srcOffset.x > unused)"""
    expect = """require(dstImage.valid())"""
    verify(registry, 'VkCopyImageInfo2', ['1.0', '1.1', '1.2', '1.3'], [], vu, {}, expect);

def test_stripped_version(registry):
    """Test when condition is stripped based on a version that is not supported."""

    vu = """unused = pAllocator.pfnAllocation
if pCreateInfo != NULL and is_version(1, 1):
  require(unused != NULL)
require(pCreateInfo.pSubpasses[0].viewMask == 0)"""
    expect = """require(pCreateInfo.pSubpasses[0].viewMask == 0)"""
    verify(registry, 'vkCreateRenderPass2', ['1.0'], [], vu, {}, expect);

    vu = """allocator = pAllocator.pfnAllocation
if pCreateInfo != NULL or is_version(1, 1):
  require(allocator != NULL)
require(pCreateInfo.pSubpasses[0].viewMask == 0)"""
    expect = """allocator = pAllocator.pfnAllocation
if pCreateInfo != NULL:
  require(allocator != NULL)
require(pCreateInfo.pSubpasses[0].viewMask == 0)"""
    verify(registry, 'vkCreateRenderPass2', ['1.0'], [], vu, {}, expect);

    vu = """allocator = pAllocator.pfnAllocation
if pCreateInfo != NULL or is_version(1, 1):
  require(allocator != NULL)
require(pCreateInfo.pSubpasses[0].viewMask == 0)"""
    expect = """allocator = pAllocator.pfnAllocation
require(allocator != NULL)
require(pCreateInfo.pSubpasses[0].viewMask == 0)"""
    verify(registry, 'vkCreateRenderPass2', ['1.0', '1.1'], [], vu, {}, expect);

    vu = """unused = pAllocator.pfnAllocation
if is_version(1, 3):
  require(unused != NULL)
require(pCreateInfo.pSubpasses[0].viewMask == 0)"""
    expect = """require(pCreateInfo.pSubpasses[0].viewMask == 0)"""
    verify(registry, 'vkCreateRenderPass2', ['1.0', '1.1', '1.2'], [], vu, {}, expect);

    vu = """allocator = pAllocator.pfnAllocation
if is_version(1, 3):
  require(allocator != NULL)
require(pCreateInfo.pSubpasses[0].viewMask == 0)"""
    expect = """allocator = pAllocator.pfnAllocation
require(allocator != NULL)
require(pCreateInfo.pSubpasses[0].viewMask == 0)"""
    verify(registry, 'vkCreateRenderPass2', ['1.0', '1.1', '1.2', '1.3'], [], vu, {}, expect);

    vu = """unused = pAllocator.pfnAllocation
if is_version(1, 3) and not is_version(1, 3):
  require(unused != NULL)
require(pCreateInfo.pSubpasses[0].viewMask == 0)"""
    expect = """require(pCreateInfo.pSubpasses[0].viewMask == 0)"""
    verify(registry, 'vkCreateRenderPass2', ['1.0', '1.1', '1.2'], [], vu, {}, expect);
    verify(registry, 'vkCreateRenderPass2', ['1.0', '1.1', '1.2', '1.3'], [], vu, {}, expect);

    vu = """unused = pAllocator.pfnAllocation
if is_version(1, 3) and not is_version(1, 3):
  require(unused != NULL)"""
    expect = None
    verify(registry, 'vkCreateRenderPass2', ['1.0', '1.1', '1.2', '1.3'], [], vu, {}, expect);

def test_stripped_extension(registry):
    """Test when condition is an extension check."""

    vu = """require(is_ext_enabled(VK_EXT_host_query_reset))"""
    expect = """require(False)"""
    verify(registry, 'vkCreateRenderPass2', ['1.0'], [], vu, {}, expect);

    vu = """if pAllocator != NULL:
        require(is_ext_enabled(VK_EXT_host_query_reset))"""
    expect = """if pAllocator != NULL:
  require(False)"""
    verify(registry, 'vkCreateRenderPass2', ['1.0'], [], vu, {}, expect);

    vu = """require(is_ext_enabled(VK_EXT_host_query_reset))"""
    expect = """require(is_ext_enabled(VK_EXT_host_query_reset))"""
    verify(registry, 'vkCreateRenderPass2', ['1.0'], ['VK_EXT_host_query_reset'], vu, {}, expect);

    vu = """if is_ext_enabled(VK_EXT_host_query_reset):
        require(pAllocator != NULL)"""
    expect = """if is_ext_enabled(VK_EXT_host_query_reset):
  require(pAllocator != NULL)"""
    verify(registry, 'vkCreateRenderPass2', ['1.0'], ['VK_EXT_host_query_reset'], vu, {}, expect);

    vu = """require(is_ext_enabled(VK_KHR_get_physical_device_properties2) or is_ext_enabled(VK_EXT_host_query_reset))"""
    expect = """require(is_ext_enabled(VK_EXT_host_query_reset))"""
    verify(registry, 'vkCreateRenderPass2', ['1.0'], ['VK_EXT_line_rasterization', 'VK_EXT_host_query_reset', 'VK_KHR_buffer_device_address'], vu, {}, expect);

    vu = """if is_ext_enabled(VK_EXT_host_query_reset) and is_ext_enabled(VK_KHR_get_physical_device_properties2):
        require(pAllocator != NULL)"""
    expect = """if (is_ext_enabled(VK_EXT_host_query_reset) and
    is_ext_enabled(VK_KHR_get_physical_device_properties2)):
  require(pAllocator != NULL)"""
    verify(registry, 'vkCreateRenderPass2', ['1.0'], ['VK_EXT_line_rasterization', 'VK_EXT_host_query_reset', 'VK_KHR_buffer_device_address', 'VK_KHR_get_physical_device_properties2'], vu, {}, expect);

    vu = """has_the_right_exts = is_ext_enabled(VK_EXT_host_query_reset) or is_ext_enabled(VK_KHR_get_physical_device_properties2)
if has_the_right_exts:
  require(pAllocator != NULL)"""
    expect = """has_the_right_exts = (is_ext_enabled(VK_EXT_host_query_reset) or
    is_ext_enabled(VK_KHR_get_physical_device_properties2))
if has_the_right_exts:
  require(pAllocator != NULL)"""
    # Note: since asciidoctor turns the extension names to lower case, the following also makes sure the checks are case-insensitive
    verify(registry, 'vkCreateRenderPass2', ['1.0'], ['vk_ext_line_rasterization', 'vk_ext_host_query_reset', 'vk_khr_buffer_device_address', 'vk_khr_get_physical_device_properties2'], vu, {}, expect);

    vu = """has_the_right_exts = is_ext_enabled(VK_EXT_host_query_reset) or is_ext_enabled(VK_KHR_get_physical_device_properties2)
if has_the_right_exts:
  require(pAllocator != NULL)"""
    expect = None
    verify(registry, 'vkCreateRenderPass2', ['1.0'], [], vu, {}, expect);

def test_stripped_features(registry):
    """Test when condition is a feature check."""

    vu = """require(is_feature_enabled(hostQueryReset))"""
    expect = """require(False)"""
    verify(registry, 'vkCreateRenderPass2', ['1.0'], [], vu, {}, expect);

    vu = """require(is_feature_enabled(hostQueryReset))"""
    expect = """require(is_feature_enabled(hostQueryReset))"""
    verify(registry, 'vkCreateRenderPass2', ['1.0'], ['VK_EXT_host_query_reset'], vu, {}, expect);
    verify(registry, 'vkCreateRenderPass2', ['1.0', '1.1', '1.2'], [], vu, {}, expect);
    verify(registry, 'vkCreateRenderPass2', ['1.0', '1.1', '1.2'], ['VK_EXT_host_query_reset'], vu, {}, expect);

    vu = """has_eds2 = is_feature_enabled(extendedDynamicState2)
if has_eds2:
  require(is_feature_enabled(extendedDynamicState))"""
    expect = None
    verify(registry, 'vkCmdDraw', ['1.0'], ['VK_EXT_host_query_reset'], vu, {}, expect);
    verify(registry, 'vkCmdDraw', ['1.0', '1.1', '1.2', '1.3'], ['VK_EXT_host_query_reset', 'VK_EXT_extended_dynamic_state'], vu, {}, expect);

    vu = """has_eds2 = is_feature_enabled(extendedDynamicState2)
if has_eds2:
  require(is_feature_enabled(extendedDynamicState))"""
    expect = """has_eds2 = is_feature_enabled(extendedDynamicState2)
if has_eds2:
  require(False)"""
    verify(registry, 'vkCmdDraw', ['1.0'], ['VK_EXT_host_query_reset', 'VK_EXT_extended_dynamic_state2'], vu, {}, expect);

    vu = """has_eds2 = is_feature_enabled(extendedDynamicState2)
if has_eds2:
  require(is_feature_enabled(extendedDynamicState))"""
    expect = """has_eds2 = is_feature_enabled(extendedDynamicState2)
if has_eds2:
  require(is_feature_enabled(extendedDynamicState))"""
    # Note: since asciidoctor turns the extension names to lower case, the following also makes sure the checks are case-insensitive
    verify(registry, 'vkCmdDraw', ['1.0', '1.1', '1.2', '1.3'], ['vk_ext_host_query_reset', 'vk_ext_extended_dynamic_state', 'vk_ext_extended_dynamic_state2'], vu, {}, expect);

    vu = """require(not is_feature_enabled(shaderDrawParameters))"""
    expect = None
    verify(registry, 'vkCmdDraw', ['1.0'], [], vu, {}, expect);

    vu = """require(not is_feature_enabled(shaderDrawParameters))"""
    expect = """require(not is_feature_enabled(shaderDrawParameters))"""
    verify(registry, 'vkCmdDraw', ['1.0', '1.1'], [], vu, {}, expect);
    verify(registry, 'vkCmdDraw', ['1.0', '1.2'], [], vu, {}, expect);
    verify(registry, 'vkCmdDraw', ['1.0', '1.1', '1.2'], [], vu, {}, expect);

def test_stripped_not(registry):
    """Test when `not` is involved."""

    vu = """require(not not is_feature_enabled(shaderDrawParameters))"""
    expect = """require(False)"""
    verify(registry, 'vkCmdDraw', ['1.0'], [], vu, {}, expect);

    vu = """require(not not is_feature_enabled(shaderDrawParameters))"""
    expect = """require(is_feature_enabled(shaderDrawParameters))"""
    verify(registry, 'vkCmdDraw', ['1.0', '1.1'], [], vu, {}, expect);
    verify(registry, 'vkCmdDraw', ['1.0', '1.2'], [], vu, {}, expect);
    verify(registry, 'vkCmdDraw', ['1.0', '1.1', '1.2'], [], vu, {}, expect);

    vu = """require(not (is_feature_enabled(shaderDrawParameters) or not flags.has_bit(VK_RENDER_PASS_CREATE_TRANSFORM_BIT_QCOM)))"""
    expect = """require(flags.has_bit(VK_RENDER_PASS_CREATE_TRANSFORM_BIT_QCOM))"""
    verify(registry, 'VkRenderPassCreateInfo2', ['1.0'], [], vu, {}, expect);

    vu = """require(not (not flags.has_bit(VK_RENDER_PASS_CREATE_TRANSFORM_BIT_QCOM) or is_feature_enabled(shaderDrawParameters)))"""
    expect = """require(flags.has_bit(VK_RENDER_PASS_CREATE_TRANSFORM_BIT_QCOM))"""
    verify(registry, 'VkRenderPassCreateInfo2', ['1.0'], [], vu, {}, expect);

    vu = """require(not (is_feature_enabled(shaderDrawParameters) or not flags.has_bit(VK_RENDER_PASS_CREATE_TRANSFORM_BIT_QCOM)))"""
    expect = """require(not (is_feature_enabled(shaderDrawParameters) or
        not flags.has_bit(VK_RENDER_PASS_CREATE_TRANSFORM_BIT_QCOM)))"""
    verify(registry, 'VkRenderPassCreateInfo2', ['1.0', '1.1'], [], vu, {}, expect);
    verify(registry, 'VkRenderPassCreateInfo2', ['1.0', '1.2'], [], vu, {}, expect);
    verify(registry, 'VkRenderPassCreateInfo2', ['1.0', '1.1', '1.2'], [], vu, {}, expect);
