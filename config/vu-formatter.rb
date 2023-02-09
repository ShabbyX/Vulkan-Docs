# Copyright 2023 The Khronos Group Inc.
#
# SPDX-License-Identifier: Apache-2.0

RUBY_ENGINE == 'opal' ? (require 'vu-formatter/extension') : (require_relative 'vu-formatter/extension')

Extensions.register do
  treeprocessor VuFormatterTreeprocessor
end
