# Copyright 2023 The Khronos Group Inc.
#
# SPDX-License-Identifier: Apache-2.0

def accumulate_attribs(current_attributes, new_attributes)
  if new_attributes.nil?
    return
  end

  new_attributes.each do |attr|
    current_attributes[attr.name] = attr.value
  end
end

def is_codified_vu(vu)
  # This function is identical to isCodifiedVU in vuAST.py. Because the vu is
  # extracted from the asciidoctor list item however, it doesn't need to
  # preprocess it the same way (stripping '*', etc).
  isIf = vu.start_with? 'if '
  isFor = vu.start_with? 'for '
  isRequire = vu.start_with? 'require('

  # Assignments are in the form `a.b.c = ...`
  isAssign = !vu[/\A[a-zA-Z0-9.]+\s*=/].nil?

  return isIf || isFor || isRequire || isAssign
end
