---
title: "Software Supply Chain"
description: "Source dependency inventory plus explicit WSL2/CI normalized security/SBOM evidence."
generated: true
audience: development
page_type: reference
confidence: generated
---

# Software Supply Chain

## Automation boundary

Heavy tools run only through explicit WSL2/CI tasks. MkDocs never invokes them. Existing Termux Trivy remains bounded and runtime-owned.

## Inventory

| Name | Version | Ecosystem | Direct? | Purpose | Runtime/dev | License | Release introduced |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Jinja2 | 3.1.6 | PyPI | yes | development Python dependency | development | unobserved until ScanCode/SBOM evidence | not-comparable |
| PyYAML | 6.0.1 | PyPI | yes | runtime Python dependency | runtime | unobserved until ScanCode/SBOM evidence | not-comparable |
| PyYAML | 6.0.3 | PyPI | yes | development Python dependency | development | unobserved until ScanCode/SBOM evidence | not-comparable |
| black | 24.0 | PyPI | yes | development Python dependency | development | unobserved until ScanCode/SBOM evidence | not-comparable |
| fastapi | 0.115.0 | PyPI | yes | runtime Python dependency | runtime | unobserved until ScanCode/SBOM evidence | not-comparable |
| httpx | 0.27 | PyPI | yes | development Python dependency | development | unobserved until ScanCode/SBOM evidence | not-comparable |
| jinja2 | 3.1 | PyPI | yes | development Python dependency | development | unobserved until ScanCode/SBOM evidence | not-comparable |
| jsonschema | 4.26 | PyPI | yes | development Python dependency | development | unobserved until ScanCode/SBOM evidence | not-comparable |
| jsonschema | 4.26.0 | PyPI | yes | development Python dependency | development | unobserved until ScanCode/SBOM evidence | not-comparable |
| mkdocs | 1.6.1 | PyPI | yes | development Python dependency | development | unobserved until ScanCode/SBOM evidence | not-comparable |
| mkdocs-material | 9.7.6 | PyPI | yes | development Python dependency | development | unobserved until ScanCode/SBOM evidence | not-comparable |
| mypy | 1.10 | PyPI | yes | development Python dependency | development | unobserved until ScanCode/SBOM evidence | not-comparable |
| nats-py | 2.7.2 | PyPI | yes | runtime Python dependency | runtime | unobserved until ScanCode/SBOM evidence | not-comparable |
| openapi-spec-validator | 0.7.2,<1.0 | PyPI | yes | development Python dependency | development | unobserved until ScanCode/SBOM evidence | not-comparable |
| pre-commit | 3.7 | PyPI | yes | development Python dependency | development | unobserved until ScanCode/SBOM evidence | not-comparable |
| pydantic | 2.7.0 | PyPI | yes | runtime Python dependency | runtime | unobserved until ScanCode/SBOM evidence | not-comparable |
| pymdown-extensions | 10.21.3 | PyPI | yes | development Python dependency | development | unobserved until ScanCode/SBOM evidence | not-comparable |
| pytest | 8.0 | PyPI | yes | development Python dependency | development | unobserved until ScanCode/SBOM evidence | not-comparable |
| pytest-asyncio | 0.23 | PyPI | yes | development Python dependency | development | unobserved until ScanCode/SBOM evidence | not-comparable |
| pytest-cov | 5.0 | PyPI | yes | development Python dependency | development | unobserved until ScanCode/SBOM evidence | not-comparable |
| pytest-timeout | 2.3 | PyPI | yes | development Python dependency | development | unobserved until ScanCode/SBOM evidence | not-comparable |
| pyyaml | 6.0 | PyPI | yes | development Python dependency | development | unobserved until ScanCode/SBOM evidence | not-comparable |
| ruff | 0.5 | PyPI | yes | development Python dependency | development | unobserved until ScanCode/SBOM evidence | not-comparable |
| uvicorn | [standard]>=0.30.0 | PyPI | yes | runtime Python dependency | runtime | unobserved until ScanCode/SBOM evidence | not-comparable |
| @acemir/cssom | 0.9.31 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @adobe/css-tools | 4.5.0 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @alloc/quick-lru | 5.2.0 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @antfu/install-pkg | 1.1.0 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @apideck/better-ajv-errors | 0.3.7 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @apidevtools/json-schema-ref-parser | 11.7.2 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @apidevtools/json-schema-ref-parser | 11.9.3 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @apidevtools/json-schema-ref-parser | 14.2.1 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @apidevtools/openapi-schemas | 2.1.0 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @apidevtools/swagger-methods | 3.0.2 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @apidevtools/swagger-parser | 10.1.1 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @asamuzakjp/css-color | 3.2.0 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @asamuzakjp/css-color | 5.1.11 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @asamuzakjp/dom-selector | 6.8.1 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @asamuzakjp/generational-cache | 1.0.1 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @asamuzakjp/nwsapi | 2.3.9 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @asyncapi/avro-schema-parser | 3.0.24 | npm | no | development/tooling dependency | development | Apache-2.0 | not-comparable |
| @asyncapi/bundler | 1.0.1 | npm | no | development/tooling dependency | development | Apache-2.0 | not-comparable |
| @asyncapi/cli | 6.0.2 | npm | yes | development/tooling dependency | development | Apache-2.0 | not-comparable |
| @asyncapi/converter | 2.0.1 | npm | no | development/tooling dependency | development | Apache-2.0 | not-comparable |
| @asyncapi/diff | 0.5.0 | npm | no | development/tooling dependency | development | Apache-2.0 | not-comparable |
| @asyncapi/generator | 3.2.2 | npm | no | development/tooling dependency | development | Apache-2.0 | not-comparable |
| @asyncapi/generator-components | 0.6.0 | npm | no | development/tooling dependency | development | Apache-2.0 | not-comparable |
| @asyncapi/generator-helpers | 1.1.0 | npm | no | development/tooling dependency | development | Apache-2.0 | not-comparable |
| @asyncapi/generator-hooks | 0.1.0 | npm | no | development/tooling dependency | development | Apache-2.0 | not-comparable |
| @asyncapi/generator-react-sdk | 1.1.3 | npm | no | development/tooling dependency | development | Apache-2.0 | not-comparable |
| @asyncapi/html-template | 3.5.6 | npm | yes | development/tooling dependency | development | Apache-2.0 | not-comparable |
| @asyncapi/modelina | 5.10.1 | npm | no | development/tooling dependency | development | Apache-2.0 | not-comparable |
| @asyncapi/modelina-cli | 5.10.1 | npm | no | development/tooling dependency | development | Apache-2.0 | not-comparable |
| @asyncapi/multi-parser | 2.3.0 | npm | no | development/tooling dependency | development | Apache-2.0 | not-comparable |
| @asyncapi/openapi-schema-parser | 3.0.24 | npm | no | development/tooling dependency | development | Apache-2.0 | not-comparable |
| @asyncapi/optimizer | 1.0.4 | npm | no | development/tooling dependency | development | Apache-2.0 | not-comparable |
| @asyncapi/parser | 3.6.0 | npm | no | development/tooling dependency | development | Apache-2.0 | not-comparable |
| @asyncapi/problem | 1.0.0 | npm | no | development/tooling dependency | development | Apache-2.0 | not-comparable |
| @asyncapi/protobuf-schema-parser | 3.6.0 | npm | no | development/tooling dependency | development | Apache-2.0 | not-comparable |
| @asyncapi/raml-dt-schema-parser | 4.0.24 | npm | no | development/tooling dependency | development | Apache-2.0 | not-comparable |
| @asyncapi/react-component | 3.1.3 | npm | no | development/tooling dependency | development | Apache-2.0 | not-comparable |
| @asyncapi/specs | 5.1.0 | npm | no | development/tooling dependency | development | Apache-2.0 | not-comparable |
| @asyncapi/specs | 6.11.1 | npm | no | development/tooling dependency | development | Apache-2.0 | not-comparable |
| @asyncapi/studio | 1.3.0 | npm | no | development/tooling dependency | development | Apache-2.0 | not-comparable |
| @aws-crypto/crc32 | 5.2.0 | npm | no | development/tooling dependency | development | Apache-2.0 | not-comparable |
| @aws-crypto/crc32c | 5.2.0 | npm | no | development/tooling dependency | development | Apache-2.0 | not-comparable |
| @aws-crypto/sha1-browser | 5.2.0 | npm | no | development/tooling dependency | development | Apache-2.0 | not-comparable |
| @aws-crypto/sha256-browser | 5.2.0 | npm | no | development/tooling dependency | development | Apache-2.0 | not-comparable |
| @aws-crypto/sha256-js | 5.2.0 | npm | no | development/tooling dependency | development | Apache-2.0 | not-comparable |
| @aws-crypto/supports-web-crypto | 5.2.0 | npm | no | development/tooling dependency | development | Apache-2.0 | not-comparable |
| @aws-crypto/util | 5.2.0 | npm | no | development/tooling dependency | development | Apache-2.0 | not-comparable |
| @aws-sdk/checksums | 3.1000.2 | npm | no | development/tooling dependency | development | Apache-2.0 | not-comparable |
| @aws-sdk/client-cloudfront | 3.1063.0 | npm | no | development/tooling dependency | development | Apache-2.0 | not-comparable |
| @aws-sdk/client-s3 | 3.1063.0 | npm | no | development/tooling dependency | development | Apache-2.0 | not-comparable |
| @aws-sdk/core | 3.974.18 | npm | no | development/tooling dependency | development | Apache-2.0 | not-comparable |
| @aws-sdk/credential-provider-env | 3.972.44 | npm | no | development/tooling dependency | development | Apache-2.0 | not-comparable |
| @aws-sdk/credential-provider-http | 3.972.46 | npm | no | development/tooling dependency | development | Apache-2.0 | not-comparable |
| @aws-sdk/credential-provider-ini | 3.972.50 | npm | no | development/tooling dependency | development | Apache-2.0 | not-comparable |
| @aws-sdk/credential-provider-login | 3.972.49 | npm | no | development/tooling dependency | development | Apache-2.0 | not-comparable |
| @aws-sdk/credential-provider-node | 3.972.52 | npm | no | development/tooling dependency | development | Apache-2.0 | not-comparable |
| @aws-sdk/credential-provider-process | 3.972.44 | npm | no | development/tooling dependency | development | Apache-2.0 | not-comparable |
| @aws-sdk/credential-provider-sso | 3.972.49 | npm | no | development/tooling dependency | development | Apache-2.0 | not-comparable |
| @aws-sdk/credential-provider-web-identity | 3.972.49 | npm | no | development/tooling dependency | development | Apache-2.0 | not-comparable |
| @aws-sdk/middleware-flexible-checksums | 3.974.27 | npm | no | development/tooling dependency | development | Apache-2.0 | not-comparable |
| @aws-sdk/middleware-sdk-s3 | 3.972.48 | npm | no | development/tooling dependency | development | Apache-2.0 | not-comparable |
| @aws-sdk/nested-clients | 3.997.17 | npm | no | development/tooling dependency | development | Apache-2.0 | not-comparable |
| @aws-sdk/signature-v4-multi-region | 3.996.32 | npm | no | development/tooling dependency | development | Apache-2.0 | not-comparable |
| @aws-sdk/token-providers | 3.1063.0 | npm | no | development/tooling dependency | development | Apache-2.0 | not-comparable |
| @aws-sdk/types | 3.973.11 | npm | no | development/tooling dependency | development | Apache-2.0 | not-comparable |
| @aws-sdk/util-locate-window | 3.965.6 | npm | no | development/tooling dependency | development | Apache-2.0 | not-comparable |
| @aws-sdk/xml-builder | 3.972.28 | npm | no | development/tooling dependency | development | Apache-2.0 | not-comparable |
| @aws/lambda-invoke-store | 0.2.4 | npm | no | development/tooling dependency | development | Apache-2.0 | not-comparable |
| @axe-core/playwright | 4.11.3 | npm | yes | development/tooling dependency | development | MPL-2.0 | not-comparable |
| @babel/code-frame | 7.29.7 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @babel/compat-data | 7.29.7 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @babel/core | 7.12.9 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @babel/core | 7.29.7 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @babel/generator | 7.29.7 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @babel/helper-annotate-as-pure | 7.29.7 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @babel/helper-compilation-targets | 7.29.7 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @babel/helper-create-class-features-plugin | 7.29.7 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @babel/helper-create-regexp-features-plugin | 7.29.7 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @babel/helper-define-polyfill-provider | 0.6.8 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @babel/helper-globals | 7.29.7 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @babel/helper-member-expression-to-functions | 7.29.7 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @babel/helper-module-imports | 7.29.7 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @babel/helper-module-transforms | 7.29.7 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @babel/helper-optimise-call-expression | 7.29.7 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @babel/helper-plugin-utils | 7.29.7 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @babel/helper-remap-async-to-generator | 7.29.7 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @babel/helper-replace-supers | 7.29.7 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @babel/helper-skip-transparent-expression-wrappers | 7.29.7 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @babel/helper-string-parser | 7.29.7 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @babel/helper-validator-identifier | 7.29.7 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @babel/helper-validator-option | 7.29.7 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @babel/helper-wrap-function | 7.29.7 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @babel/helpers | 7.29.7 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @babel/parser | 7.29.7 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @babel/plugin-bugfix-firefox-class-in-computed-class-key | 7.29.7 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @babel/plugin-bugfix-safari-class-field-initializer-scope | 7.29.7 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @babel/plugin-bugfix-safari-id-destructuring-collision-in-function-expression | 7.29.7 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @babel/plugin-bugfix-safari-rest-destructuring-rhs-array | 7.29.7 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @babel/plugin-bugfix-v8-spread-parameters-in-optional-chaining | 7.29.7 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @babel/plugin-bugfix-v8-static-class-fields-redefine-readonly | 7.29.7 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @babel/plugin-proposal-private-property-in-object | 7.21.0-placeholder-for-preset-env.2 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @babel/plugin-syntax-import-assertions | 7.29.7 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @babel/plugin-syntax-import-attributes | 7.29.7 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @babel/plugin-syntax-jsx | 7.29.7 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @babel/plugin-syntax-unicode-sets-regex | 7.18.6 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @babel/plugin-transform-arrow-functions | 7.29.7 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @babel/plugin-transform-async-generator-functions | 7.29.7 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @babel/plugin-transform-async-to-generator | 7.29.7 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @babel/plugin-transform-block-scoped-functions | 7.29.7 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @babel/plugin-transform-block-scoping | 7.29.7 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @babel/plugin-transform-class-properties | 7.29.7 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @babel/plugin-transform-class-static-block | 7.29.7 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @babel/plugin-transform-classes | 7.29.7 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @babel/plugin-transform-computed-properties | 7.29.7 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @babel/plugin-transform-destructuring | 7.29.7 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @babel/plugin-transform-dotall-regex | 7.29.7 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @babel/plugin-transform-duplicate-keys | 7.29.7 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @babel/plugin-transform-duplicate-named-capturing-groups-regex | 7.29.7 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @babel/plugin-transform-dynamic-import | 7.29.7 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @babel/plugin-transform-explicit-resource-management | 7.29.7 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @babel/plugin-transform-exponentiation-operator | 7.29.7 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @babel/plugin-transform-export-namespace-from | 7.29.7 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @babel/plugin-transform-for-of | 7.29.7 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @babel/plugin-transform-function-name | 7.29.7 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @babel/plugin-transform-json-strings | 7.29.7 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @babel/plugin-transform-literals | 7.29.7 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @babel/plugin-transform-logical-assignment-operators | 7.29.7 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @babel/plugin-transform-member-expression-literals | 7.29.7 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @babel/plugin-transform-modules-amd | 7.29.7 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @babel/plugin-transform-modules-commonjs | 7.29.7 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @babel/plugin-transform-modules-systemjs | 7.29.7 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @babel/plugin-transform-modules-umd | 7.29.7 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @babel/plugin-transform-named-capturing-groups-regex | 7.29.7 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @babel/plugin-transform-new-target | 7.29.7 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @babel/plugin-transform-nullish-coalescing-operator | 7.29.7 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @babel/plugin-transform-numeric-separator | 7.29.7 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @babel/plugin-transform-object-rest-spread | 7.29.7 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @babel/plugin-transform-object-super | 7.29.7 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @babel/plugin-transform-optional-catch-binding | 7.29.7 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @babel/plugin-transform-optional-chaining | 7.29.7 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @babel/plugin-transform-parameters | 7.29.7 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @babel/plugin-transform-private-methods | 7.29.7 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @babel/plugin-transform-private-property-in-object | 7.29.7 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @babel/plugin-transform-property-literals | 7.29.7 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @babel/plugin-transform-react-display-name | 7.29.7 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @babel/plugin-transform-react-jsx | 7.29.7 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @babel/plugin-transform-react-jsx-development | 7.29.7 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @babel/plugin-transform-react-jsx-self | 7.29.7 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @babel/plugin-transform-react-jsx-source | 7.29.7 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @babel/plugin-transform-react-pure-annotations | 7.29.7 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @babel/plugin-transform-regenerator | 7.29.7 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @babel/plugin-transform-regexp-modifiers | 7.29.7 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @babel/plugin-transform-reserved-words | 7.29.7 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @babel/plugin-transform-shorthand-properties | 7.29.7 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @babel/plugin-transform-spread | 7.29.7 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @babel/plugin-transform-sticky-regex | 7.29.7 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @babel/plugin-transform-template-literals | 7.29.7 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @babel/plugin-transform-typeof-symbol | 7.29.7 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @babel/plugin-transform-unicode-escapes | 7.29.7 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @babel/plugin-transform-unicode-property-regex | 7.29.7 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @babel/plugin-transform-unicode-regex | 7.29.7 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @babel/plugin-transform-unicode-sets-regex | 7.29.7 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @babel/preset-env | 7.29.7 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @babel/preset-modules | 0.1.6-no-external-plugins | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @babel/preset-react | 7.29.7 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @babel/runtime | 7.29.7 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @babel/template | 7.29.7 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @babel/traverse | 7.29.7 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @babel/types | 7.29.7 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @braintree/sanitize-url | 7.1.2 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @bramus/specificity | 2.4.2 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @changesets/changelog-git | 0.2.1 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @changesets/types | 6.1.0 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @chevrotain/types | 11.1.2 | npm | no | development/tooling dependency | development | Apache-2.0 | not-comparable |
| @clack/core | 0.5.0 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @clack/prompts | 0.11.0 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @codemirror/autocomplete | 6.20.3 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @codemirror/commands | 6.10.3 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @codemirror/language | 6.12.3 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @codemirror/lint | 6.9.6 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @codemirror/search | 6.7.0 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @codemirror/state | 6.6.0 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @codemirror/view | 6.43.0 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @colors/colors | 1.6.0 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @cspotcode/source-map-support | 0.8.1 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @csstools/color-helpers | 5.1.0 | npm | no | development/tooling dependency | development | MIT-0 | not-comparable |
| @csstools/color-helpers | 6.0.2 | npm | no | development/tooling dependency | development | MIT-0 | not-comparable |
| @csstools/css-calc | 2.1.4 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @csstools/css-calc | 3.2.1 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @csstools/css-color-parser | 3.1.0 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @csstools/css-color-parser | 4.1.1 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @csstools/css-parser-algorithms | 3.0.5 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @csstools/css-parser-algorithms | 4.0.0 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @csstools/css-syntax-patches-for-csstree | 1.1.5 | npm | no | development/tooling dependency | development | MIT-0 | not-comparable |
| @csstools/css-tokenizer | 3.0.4 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @csstools/css-tokenizer | 4.0.0 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @dabh/diagnostics | 2.0.8 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @ebay/nice-modal-react | 1.2.13 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @emotion/is-prop-valid | 1.4.0 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @emotion/memoize | 0.9.0 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @esbuild/aix-ppc64 | 0.21.5 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @esbuild/aix-ppc64 | 0.25.12 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @esbuild/android-arm | 0.21.5 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @esbuild/android-arm | 0.25.12 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @esbuild/android-arm64 | 0.21.5 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @esbuild/android-arm64 | 0.25.12 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @esbuild/android-x64 | 0.21.5 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @esbuild/android-x64 | 0.25.12 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @esbuild/darwin-arm64 | 0.21.5 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @esbuild/darwin-arm64 | 0.25.12 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @esbuild/darwin-x64 | 0.21.5 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @esbuild/darwin-x64 | 0.25.12 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @esbuild/freebsd-arm64 | 0.21.5 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @esbuild/freebsd-arm64 | 0.25.12 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @esbuild/freebsd-x64 | 0.21.5 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @esbuild/freebsd-x64 | 0.25.12 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @esbuild/linux-arm | 0.21.5 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @esbuild/linux-arm | 0.25.12 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @esbuild/linux-arm64 | 0.21.5 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @esbuild/linux-arm64 | 0.25.12 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @esbuild/linux-ia32 | 0.21.5 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @esbuild/linux-ia32 | 0.25.12 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @esbuild/linux-loong64 | 0.21.5 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @esbuild/linux-loong64 | 0.25.12 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @esbuild/linux-mips64el | 0.21.5 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @esbuild/linux-mips64el | 0.25.12 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @esbuild/linux-ppc64 | 0.21.5 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @esbuild/linux-ppc64 | 0.25.12 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @esbuild/linux-riscv64 | 0.21.5 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @esbuild/linux-riscv64 | 0.25.12 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @esbuild/linux-s390x | 0.21.5 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @esbuild/linux-s390x | 0.25.12 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @esbuild/linux-x64 | 0.21.5 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @esbuild/linux-x64 | 0.25.12 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @esbuild/netbsd-arm64 | 0.25.12 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @esbuild/netbsd-x64 | 0.21.5 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @esbuild/netbsd-x64 | 0.25.12 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @esbuild/openbsd-arm64 | 0.25.12 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @esbuild/openbsd-x64 | 0.21.5 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @esbuild/openbsd-x64 | 0.25.12 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @esbuild/openharmony-arm64 | 0.25.12 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @esbuild/sunos-x64 | 0.21.5 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @esbuild/sunos-x64 | 0.25.12 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @esbuild/win32-arm64 | 0.21.5 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @esbuild/win32-arm64 | 0.25.12 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @esbuild/win32-ia32 | 0.21.5 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @esbuild/win32-ia32 | 0.25.12 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @esbuild/win32-x64 | 0.21.5 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @esbuild/win32-x64 | 0.25.12 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @eslint-community/eslint-utils | 4.9.1 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @eslint-community/regexpp | 4.12.2 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @eslint/eslintrc | 2.1.4 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @eslint/js | 8.57.1 | npm | yes | development/tooling dependency | development | MIT | not-comparable |
| @eslint/js | 9.39.4 | npm | yes | development/tooling dependency | development | MIT | not-comparable |
| @exodus/bytes | 1.15.1 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @exodus/schemasafe | 1.3.0 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @faker-js/faker | 7.6.0 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @formatjs/ecma402-abstract | 2.3.6 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @formatjs/fast-memoize | 2.2.7 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @formatjs/icu-messageformat-parser | 2.11.4 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @formatjs/icu-skeleton-parser | 1.8.16 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @formatjs/intl-localematcher | 0.6.2 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @gar/promise-retry | 1.0.3 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @gar/promisify | 1.1.3 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @hapi/address | 5.1.1 | npm | no | development/tooling dependency | development | BSD-3-Clause | not-comparable |
| @hapi/formula | 3.0.2 | npm | no | development/tooling dependency | development | BSD-3-Clause | not-comparable |
| @hapi/hoek | 11.0.7 | npm | no | development/tooling dependency | development | BSD-3-Clause | not-comparable |
| @hapi/pinpoint | 2.0.1 | npm | no | development/tooling dependency | development | BSD-3-Clause | not-comparable |
| @hapi/tlds | 1.1.6 | npm | no | development/tooling dependency | development | BSD-3-Clause | not-comparable |
| @hapi/topo | 6.0.2 | npm | no | development/tooling dependency | development | BSD-3-Clause | not-comparable |
| @headlessui/react | 1.7.19 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @hookstate/core | 4.0.2 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @humanwhocodes/config-array | 0.13.0 | npm | no | development/tooling dependency | development | Apache-2.0 | not-comparable |
| @humanwhocodes/module-importer | 1.0.1 | npm | no | development/tooling dependency | development | Apache-2.0 | not-comparable |
| @humanwhocodes/momoa | 2.0.4 | npm | no | development/tooling dependency | development | Apache-2.0 | not-comparable |
| @humanwhocodes/object-schema | 2.0.3 | npm | no | development/tooling dependency | development | BSD-3-Clause | not-comparable |
| @hyperjump/json | 0.1.0 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @hyperjump/json-pointer | 0.9.8 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @hyperjump/json-schema | 0.23.5 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @hyperjump/json-schema-core | 0.28.5 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @hyperjump/pact | 0.2.5 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @iconify/types | 2.0.0 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @iconify/utils | 3.1.3 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @inquirer/ansi | 1.0.2 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @inquirer/ansi | 2.0.7 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @inquirer/checkbox | 4.3.2 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @inquirer/confirm | 3.2.0 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @inquirer/confirm | 5.1.21 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @inquirer/confirm | 6.1.1 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @inquirer/core | 10.3.2 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @inquirer/core | 11.2.1 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @inquirer/core | 9.2.1 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @inquirer/editor | 4.2.23 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @inquirer/expand | 4.0.23 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @inquirer/external-editor | 1.0.3 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @inquirer/figures | 1.0.15 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @inquirer/figures | 2.0.7 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @inquirer/input | 2.3.0 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @inquirer/input | 4.3.1 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @inquirer/number | 3.0.23 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @inquirer/password | 4.0.23 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @inquirer/prompts | 7.10.1 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @inquirer/rawlist | 4.1.11 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @inquirer/search | 3.2.2 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @inquirer/select | 2.5.0 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @inquirer/select | 4.4.2 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @inquirer/type | 1.5.5 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @inquirer/type | 2.0.0 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @inquirer/type | 3.0.10 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @inquirer/type | 4.0.7 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @isaacs/cliui | 8.0.2 | npm | no | development/tooling dependency | development | ISC | not-comparable |
| @isaacs/cliui | 9.0.0 | npm | no | development/tooling dependency | development | BlueOak-1.0.0 | not-comparable |
| @isaacs/fs-minipass | 4.0.1 | npm | no | development/tooling dependency | development | ISC | not-comparable |
| @isaacs/string-locale-compare | 1.1.0 | npm | no | development/tooling dependency | development | ISC | not-comparable |
| @joshwooding/vite-plugin-react-docgen-typescript | 0.5.0 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @jridgewell/gen-mapping | 0.3.13 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @jridgewell/remapping | 2.3.5 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @jridgewell/resolve-uri | 3.1.2 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @jridgewell/source-map | 0.3.11 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @jridgewell/sourcemap-codec | 1.5.5 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @jridgewell/trace-mapping | 0.3.31 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @jridgewell/trace-mapping | 0.3.9 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @jsdevtools/ono | 7.1.3 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @jsep-plugin/assignment | 1.3.0 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @jsep-plugin/regex | 1.0.4 | npm | no | development/tooling dependency | development | MIT | not-comparable |
| @jsep-plugin/ternary | 1.1.4 | npm | no | development/tooling dependency | development | MIT | not-comparable |

## Canonical promoted tool artifacts

| Artifact | Present |
| --- | --- |
| sbom-dev.cdx.json | yes |
| sbom-release.cdx.json | yes |
| sbom-runtime.cdx.json | yes |
| vulnerability-correlation.json | yes |
| license-inventory.json | yes |
| security-analysis.json | yes |
| scorecard-checks.json | yes |

## Optional Dependency-Track

`task lite:docs:supply-chain:dependency-track:export` stages canonical CycloneDX files for optional import. Documentation never depends on a live Dependency-Track service.
