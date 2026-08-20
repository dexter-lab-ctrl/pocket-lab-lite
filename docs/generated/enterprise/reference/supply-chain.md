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
| Jinja2 | 3.1.6 | PyPI | yes | development Python dependency | development | unobserved until ScanCode/SBOM evidence | present-in-baseline |
| PyYAML | 6.0.1 | PyPI | yes | runtime Python dependency | runtime | unobserved until ScanCode/SBOM evidence | present-in-baseline |
| PyYAML | 6.0.3 | PyPI | yes | development Python dependency | development | unobserved until ScanCode/SBOM evidence | present-in-baseline |
| black | 24.0 | PyPI | yes | development Python dependency | development | unobserved until ScanCode/SBOM evidence | present-in-baseline |
| fastapi | 0.115.0 | PyPI | yes | runtime Python dependency | runtime | unobserved until ScanCode/SBOM evidence | present-in-baseline |
| httpx | 0.27 | PyPI | yes | development Python dependency | development | unobserved until ScanCode/SBOM evidence | present-in-baseline |
| jinja2 | 3.1 | PyPI | yes | development Python dependency | development | unobserved until ScanCode/SBOM evidence | present-in-baseline |
| jsonschema | 4.26 | PyPI | yes | development Python dependency | development | unobserved until ScanCode/SBOM evidence | present-in-baseline |
| jsonschema | 4.26.0 | PyPI | yes | development Python dependency | development | unobserved until ScanCode/SBOM evidence | present-in-baseline |
| mkdocs | 1.6.1 | PyPI | yes | development Python dependency | development | unobserved until ScanCode/SBOM evidence | present-in-baseline |
| mkdocs-material | 9.7.6 | PyPI | yes | development Python dependency | development | unobserved until ScanCode/SBOM evidence | present-in-baseline |
| mypy | 1.10 | PyPI | yes | development Python dependency | development | unobserved until ScanCode/SBOM evidence | present-in-baseline |
| nats-py | 2.7.2 | PyPI | yes | runtime Python dependency | runtime | unobserved until ScanCode/SBOM evidence | present-in-baseline |
| openapi-spec-validator | 0.7.2,<1.0 | PyPI | yes | development Python dependency | development | unobserved until ScanCode/SBOM evidence | present-in-baseline |
| pre-commit | 3.7 | PyPI | yes | development Python dependency | development | unobserved until ScanCode/SBOM evidence | present-in-baseline |
| pydantic | 2.7.0 | PyPI | yes | runtime Python dependency | runtime | unobserved until ScanCode/SBOM evidence | present-in-baseline |
| pymdown-extensions | 10.21.3 | PyPI | yes | development Python dependency | development | unobserved until ScanCode/SBOM evidence | present-in-baseline |
| pytest | 8.0 | PyPI | yes | development Python dependency | development | unobserved until ScanCode/SBOM evidence | present-in-baseline |
| pytest-asyncio | 0.23 | PyPI | yes | development Python dependency | development | unobserved until ScanCode/SBOM evidence | present-in-baseline |
| pytest-cov | 5.0 | PyPI | yes | development Python dependency | development | unobserved until ScanCode/SBOM evidence | present-in-baseline |
| pytest-timeout | 2.3 | PyPI | yes | development Python dependency | development | unobserved until ScanCode/SBOM evidence | present-in-baseline |
| pyyaml | 6.0 | PyPI | yes | development Python dependency | development | unobserved until ScanCode/SBOM evidence | present-in-baseline |
| ruff | 0.5 | PyPI | yes | development Python dependency | development | unobserved until ScanCode/SBOM evidence | present-in-baseline |
| uvicorn | [standard]>=0.30.0 | PyPI | yes | runtime Python dependency | runtime | unobserved until ScanCode/SBOM evidence | present-in-baseline |
| @acemir/cssom | 0.9.31 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @adobe/css-tools | 4.5.0 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @alloc/quick-lru | 5.2.0 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @antfu/install-pkg | 1.1.0 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @apideck/better-ajv-errors | 0.3.7 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @apidevtools/json-schema-ref-parser | 11.7.2 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @apidevtools/json-schema-ref-parser | 11.9.3 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @apidevtools/json-schema-ref-parser | 14.2.1 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @apidevtools/openapi-schemas | 2.1.0 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @apidevtools/swagger-methods | 3.0.2 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @apidevtools/swagger-parser | 10.1.1 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @asamuzakjp/css-color | 3.2.0 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @asamuzakjp/css-color | 5.1.11 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @asamuzakjp/dom-selector | 6.8.1 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @asamuzakjp/generational-cache | 1.0.1 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @asamuzakjp/nwsapi | 2.3.9 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @asyncapi/avro-schema-parser | 3.0.24 | npm | no | development/tooling dependency | development | Apache-2.0 | present-in-baseline |
| @asyncapi/bundler | 1.0.1 | npm | no | development/tooling dependency | development | Apache-2.0 | present-in-baseline |
| @asyncapi/cli | 6.0.2 | npm | yes | development/tooling dependency | development | Apache-2.0 | present-in-baseline |
| @asyncapi/converter | 2.0.1 | npm | no | development/tooling dependency | development | Apache-2.0 | present-in-baseline |
| @asyncapi/diff | 0.5.0 | npm | no | development/tooling dependency | development | Apache-2.0 | present-in-baseline |
| @asyncapi/generator | 3.2.2 | npm | no | development/tooling dependency | development | Apache-2.0 | present-in-baseline |
| @asyncapi/generator-components | 0.6.0 | npm | no | development/tooling dependency | development | Apache-2.0 | present-in-baseline |
| @asyncapi/generator-helpers | 1.1.0 | npm | no | development/tooling dependency | development | Apache-2.0 | present-in-baseline |
| @asyncapi/generator-hooks | 0.1.0 | npm | no | development/tooling dependency | development | Apache-2.0 | present-in-baseline |
| @asyncapi/generator-react-sdk | 1.1.3 | npm | no | development/tooling dependency | development | Apache-2.0 | present-in-baseline |
| @asyncapi/html-template | 3.5.6 | npm | yes | development/tooling dependency | development | Apache-2.0 | present-in-baseline |
| @asyncapi/modelina | 5.10.1 | npm | no | development/tooling dependency | development | Apache-2.0 | present-in-baseline |
| @asyncapi/modelina-cli | 5.10.1 | npm | no | development/tooling dependency | development | Apache-2.0 | present-in-baseline |
| @asyncapi/multi-parser | 2.3.0 | npm | no | development/tooling dependency | development | Apache-2.0 | present-in-baseline |
| @asyncapi/openapi-schema-parser | 3.0.24 | npm | no | development/tooling dependency | development | Apache-2.0 | present-in-baseline |
| @asyncapi/optimizer | 1.0.4 | npm | no | development/tooling dependency | development | Apache-2.0 | present-in-baseline |
| @asyncapi/parser | 3.6.0 | npm | no | development/tooling dependency | development | Apache-2.0 | present-in-baseline |
| @asyncapi/problem | 1.0.0 | npm | no | development/tooling dependency | development | Apache-2.0 | present-in-baseline |
| @asyncapi/protobuf-schema-parser | 3.6.0 | npm | no | development/tooling dependency | development | Apache-2.0 | present-in-baseline |
| @asyncapi/raml-dt-schema-parser | 4.0.24 | npm | no | development/tooling dependency | development | Apache-2.0 | present-in-baseline |
| @asyncapi/react-component | 3.1.3 | npm | no | development/tooling dependency | development | Apache-2.0 | present-in-baseline |
| @asyncapi/specs | 5.1.0 | npm | no | development/tooling dependency | development | Apache-2.0 | present-in-baseline |
| @asyncapi/specs | 6.11.1 | npm | no | development/tooling dependency | development | Apache-2.0 | present-in-baseline |
| @asyncapi/studio | 1.3.0 | npm | no | development/tooling dependency | development | Apache-2.0 | present-in-baseline |
| @aws-crypto/crc32 | 5.2.0 | npm | no | development/tooling dependency | development | Apache-2.0 | present-in-baseline |
| @aws-crypto/crc32c | 5.2.0 | npm | no | development/tooling dependency | development | Apache-2.0 | present-in-baseline |
| @aws-crypto/sha1-browser | 5.2.0 | npm | no | development/tooling dependency | development | Apache-2.0 | present-in-baseline |
| @aws-crypto/sha256-browser | 5.2.0 | npm | no | development/tooling dependency | development | Apache-2.0 | present-in-baseline |
| @aws-crypto/sha256-js | 5.2.0 | npm | no | development/tooling dependency | development | Apache-2.0 | present-in-baseline |
| @aws-crypto/supports-web-crypto | 5.2.0 | npm | no | development/tooling dependency | development | Apache-2.0 | present-in-baseline |
| @aws-crypto/util | 5.2.0 | npm | no | development/tooling dependency | development | Apache-2.0 | present-in-baseline |
| @aws-sdk/checksums | 3.1000.2 | npm | no | development/tooling dependency | development | Apache-2.0 | present-in-baseline |
| @aws-sdk/client-cloudfront | 3.1063.0 | npm | no | development/tooling dependency | development | Apache-2.0 | present-in-baseline |
| @aws-sdk/client-s3 | 3.1063.0 | npm | no | development/tooling dependency | development | Apache-2.0 | present-in-baseline |
| @aws-sdk/core | 3.974.18 | npm | no | development/tooling dependency | development | Apache-2.0 | present-in-baseline |
| @aws-sdk/credential-provider-env | 3.972.44 | npm | no | development/tooling dependency | development | Apache-2.0 | present-in-baseline |
| @aws-sdk/credential-provider-http | 3.972.46 | npm | no | development/tooling dependency | development | Apache-2.0 | present-in-baseline |
| @aws-sdk/credential-provider-ini | 3.972.50 | npm | no | development/tooling dependency | development | Apache-2.0 | present-in-baseline |
| @aws-sdk/credential-provider-login | 3.972.49 | npm | no | development/tooling dependency | development | Apache-2.0 | present-in-baseline |
| @aws-sdk/credential-provider-node | 3.972.52 | npm | no | development/tooling dependency | development | Apache-2.0 | present-in-baseline |
| @aws-sdk/credential-provider-process | 3.972.44 | npm | no | development/tooling dependency | development | Apache-2.0 | present-in-baseline |
| @aws-sdk/credential-provider-sso | 3.972.49 | npm | no | development/tooling dependency | development | Apache-2.0 | present-in-baseline |
| @aws-sdk/credential-provider-web-identity | 3.972.49 | npm | no | development/tooling dependency | development | Apache-2.0 | present-in-baseline |
| @aws-sdk/middleware-flexible-checksums | 3.974.27 | npm | no | development/tooling dependency | development | Apache-2.0 | present-in-baseline |
| @aws-sdk/middleware-sdk-s3 | 3.972.48 | npm | no | development/tooling dependency | development | Apache-2.0 | present-in-baseline |
| @aws-sdk/nested-clients | 3.997.17 | npm | no | development/tooling dependency | development | Apache-2.0 | present-in-baseline |
| @aws-sdk/signature-v4-multi-region | 3.996.32 | npm | no | development/tooling dependency | development | Apache-2.0 | present-in-baseline |
| @aws-sdk/token-providers | 3.1063.0 | npm | no | development/tooling dependency | development | Apache-2.0 | present-in-baseline |
| @aws-sdk/types | 3.973.11 | npm | no | development/tooling dependency | development | Apache-2.0 | present-in-baseline |
| @aws-sdk/util-locate-window | 3.965.6 | npm | no | development/tooling dependency | development | Apache-2.0 | present-in-baseline |
| @aws-sdk/xml-builder | 3.972.28 | npm | no | development/tooling dependency | development | Apache-2.0 | present-in-baseline |
| @aws/lambda-invoke-store | 0.2.4 | npm | no | development/tooling dependency | development | Apache-2.0 | present-in-baseline |
| @axe-core/playwright | 4.11.3 | npm | yes | development/tooling dependency | development | MPL-2.0 | present-in-baseline |
| @babel/code-frame | 7.29.7 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @babel/compat-data | 7.29.7 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @babel/core | 7.12.9 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @babel/core | 7.29.7 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @babel/generator | 7.29.7 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @babel/helper-annotate-as-pure | 7.29.7 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @babel/helper-compilation-targets | 7.29.7 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @babel/helper-create-class-features-plugin | 7.29.7 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @babel/helper-create-regexp-features-plugin | 7.29.7 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @babel/helper-define-polyfill-provider | 0.6.8 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @babel/helper-globals | 7.29.7 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @babel/helper-member-expression-to-functions | 7.29.7 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @babel/helper-module-imports | 7.29.7 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @babel/helper-module-transforms | 7.29.7 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @babel/helper-optimise-call-expression | 7.29.7 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @babel/helper-plugin-utils | 7.29.7 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @babel/helper-remap-async-to-generator | 7.29.7 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @babel/helper-replace-supers | 7.29.7 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @babel/helper-skip-transparent-expression-wrappers | 7.29.7 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @babel/helper-string-parser | 7.29.7 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @babel/helper-validator-identifier | 7.29.7 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @babel/helper-validator-option | 7.29.7 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @babel/helper-wrap-function | 7.29.7 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @babel/helpers | 7.29.7 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @babel/parser | 7.29.7 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @babel/plugin-bugfix-firefox-class-in-computed-class-key | 7.29.7 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @babel/plugin-bugfix-safari-class-field-initializer-scope | 7.29.7 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @babel/plugin-bugfix-safari-id-destructuring-collision-in-function-expression | 7.29.7 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @babel/plugin-bugfix-safari-rest-destructuring-rhs-array | 7.29.7 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @babel/plugin-bugfix-v8-spread-parameters-in-optional-chaining | 7.29.7 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @babel/plugin-bugfix-v8-static-class-fields-redefine-readonly | 7.29.7 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @babel/plugin-proposal-private-property-in-object | 7.21.0-placeholder-for-preset-env.2 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @babel/plugin-syntax-import-assertions | 7.29.7 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @babel/plugin-syntax-import-attributes | 7.29.7 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @babel/plugin-syntax-jsx | 7.29.7 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @babel/plugin-syntax-unicode-sets-regex | 7.18.6 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @babel/plugin-transform-arrow-functions | 7.29.7 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @babel/plugin-transform-async-generator-functions | 7.29.7 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @babel/plugin-transform-async-to-generator | 7.29.7 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @babel/plugin-transform-block-scoped-functions | 7.29.7 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @babel/plugin-transform-block-scoping | 7.29.7 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @babel/plugin-transform-class-properties | 7.29.7 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @babel/plugin-transform-class-static-block | 7.29.7 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @babel/plugin-transform-classes | 7.29.7 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @babel/plugin-transform-computed-properties | 7.29.7 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @babel/plugin-transform-destructuring | 7.29.7 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @babel/plugin-transform-dotall-regex | 7.29.7 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @babel/plugin-transform-duplicate-keys | 7.29.7 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @babel/plugin-transform-duplicate-named-capturing-groups-regex | 7.29.7 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @babel/plugin-transform-dynamic-import | 7.29.7 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @babel/plugin-transform-explicit-resource-management | 7.29.7 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @babel/plugin-transform-exponentiation-operator | 7.29.7 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @babel/plugin-transform-export-namespace-from | 7.29.7 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @babel/plugin-transform-for-of | 7.29.7 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @babel/plugin-transform-function-name | 7.29.7 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @babel/plugin-transform-json-strings | 7.29.7 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @babel/plugin-transform-literals | 7.29.7 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @babel/plugin-transform-logical-assignment-operators | 7.29.7 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @babel/plugin-transform-member-expression-literals | 7.29.7 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @babel/plugin-transform-modules-amd | 7.29.7 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @babel/plugin-transform-modules-commonjs | 7.29.7 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @babel/plugin-transform-modules-systemjs | 7.29.7 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @babel/plugin-transform-modules-umd | 7.29.7 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @babel/plugin-transform-named-capturing-groups-regex | 7.29.7 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @babel/plugin-transform-new-target | 7.29.7 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @babel/plugin-transform-nullish-coalescing-operator | 7.29.7 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @babel/plugin-transform-numeric-separator | 7.29.7 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @babel/plugin-transform-object-rest-spread | 7.29.7 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @babel/plugin-transform-object-super | 7.29.7 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @babel/plugin-transform-optional-catch-binding | 7.29.7 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @babel/plugin-transform-optional-chaining | 7.29.7 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @babel/plugin-transform-parameters | 7.29.7 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @babel/plugin-transform-private-methods | 7.29.7 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @babel/plugin-transform-private-property-in-object | 7.29.7 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @babel/plugin-transform-property-literals | 7.29.7 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @babel/plugin-transform-react-display-name | 7.29.7 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @babel/plugin-transform-react-jsx | 7.29.7 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @babel/plugin-transform-react-jsx-development | 7.29.7 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @babel/plugin-transform-react-jsx-self | 7.29.7 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @babel/plugin-transform-react-jsx-source | 7.29.7 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @babel/plugin-transform-react-pure-annotations | 7.29.7 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @babel/plugin-transform-regenerator | 7.29.7 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @babel/plugin-transform-regexp-modifiers | 7.29.7 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @babel/plugin-transform-reserved-words | 7.29.7 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @babel/plugin-transform-shorthand-properties | 7.29.7 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @babel/plugin-transform-spread | 7.29.7 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @babel/plugin-transform-sticky-regex | 7.29.7 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @babel/plugin-transform-template-literals | 7.29.7 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @babel/plugin-transform-typeof-symbol | 7.29.7 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @babel/plugin-transform-unicode-escapes | 7.29.7 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @babel/plugin-transform-unicode-property-regex | 7.29.7 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @babel/plugin-transform-unicode-regex | 7.29.7 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @babel/plugin-transform-unicode-sets-regex | 7.29.7 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @babel/preset-env | 7.29.7 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @babel/preset-modules | 0.1.6-no-external-plugins | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @babel/preset-react | 7.29.7 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @babel/runtime | 7.29.7 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @babel/template | 7.29.7 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @babel/traverse | 7.29.7 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @babel/types | 7.29.7 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @braintree/sanitize-url | 7.1.2 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @bramus/specificity | 2.4.2 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @changesets/changelog-git | 0.2.1 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @changesets/types | 6.1.0 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @chevrotain/types | 11.1.2 | npm | no | development/tooling dependency | development | Apache-2.0 | present-in-baseline |
| @clack/core | 0.5.0 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @clack/prompts | 0.11.0 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @codemirror/autocomplete | 6.20.3 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @codemirror/commands | 6.10.3 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @codemirror/language | 6.12.3 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @codemirror/lint | 6.9.6 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @codemirror/search | 6.7.0 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @codemirror/state | 6.6.0 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @codemirror/view | 6.43.0 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @colors/colors | 1.6.0 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @cspotcode/source-map-support | 0.8.1 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @csstools/color-helpers | 5.1.0 | npm | no | development/tooling dependency | development | MIT-0 | present-in-baseline |
| @csstools/color-helpers | 6.0.2 | npm | no | development/tooling dependency | development | MIT-0 | present-in-baseline |
| @csstools/css-calc | 2.1.4 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @csstools/css-calc | 3.2.1 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @csstools/css-color-parser | 3.1.0 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @csstools/css-color-parser | 4.1.1 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @csstools/css-parser-algorithms | 3.0.5 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @csstools/css-parser-algorithms | 4.0.0 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @csstools/css-syntax-patches-for-csstree | 1.1.5 | npm | no | development/tooling dependency | development | MIT-0 | present-in-baseline |
| @csstools/css-tokenizer | 3.0.4 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @csstools/css-tokenizer | 4.0.0 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @dabh/diagnostics | 2.0.8 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @ebay/nice-modal-react | 1.2.13 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @emotion/is-prop-valid | 1.4.0 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @emotion/memoize | 0.9.0 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @esbuild/aix-ppc64 | 0.21.5 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @esbuild/aix-ppc64 | 0.25.12 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @esbuild/android-arm | 0.21.5 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @esbuild/android-arm | 0.25.12 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @esbuild/android-arm64 | 0.21.5 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @esbuild/android-arm64 | 0.25.12 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @esbuild/android-x64 | 0.21.5 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @esbuild/android-x64 | 0.25.12 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @esbuild/darwin-arm64 | 0.21.5 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @esbuild/darwin-arm64 | 0.25.12 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @esbuild/darwin-x64 | 0.21.5 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @esbuild/darwin-x64 | 0.25.12 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @esbuild/freebsd-arm64 | 0.21.5 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @esbuild/freebsd-arm64 | 0.25.12 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @esbuild/freebsd-x64 | 0.21.5 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @esbuild/freebsd-x64 | 0.25.12 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @esbuild/linux-arm | 0.21.5 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @esbuild/linux-arm | 0.25.12 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @esbuild/linux-arm64 | 0.21.5 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @esbuild/linux-arm64 | 0.25.12 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @esbuild/linux-ia32 | 0.21.5 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @esbuild/linux-ia32 | 0.25.12 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @esbuild/linux-loong64 | 0.21.5 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @esbuild/linux-loong64 | 0.25.12 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @esbuild/linux-mips64el | 0.21.5 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @esbuild/linux-mips64el | 0.25.12 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @esbuild/linux-ppc64 | 0.21.5 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @esbuild/linux-ppc64 | 0.25.12 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @esbuild/linux-riscv64 | 0.21.5 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @esbuild/linux-riscv64 | 0.25.12 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @esbuild/linux-s390x | 0.21.5 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @esbuild/linux-s390x | 0.25.12 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @esbuild/linux-x64 | 0.21.5 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @esbuild/linux-x64 | 0.25.12 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @esbuild/netbsd-arm64 | 0.25.12 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @esbuild/netbsd-x64 | 0.21.5 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @esbuild/netbsd-x64 | 0.25.12 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @esbuild/openbsd-arm64 | 0.25.12 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @esbuild/openbsd-x64 | 0.21.5 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @esbuild/openbsd-x64 | 0.25.12 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @esbuild/openharmony-arm64 | 0.25.12 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @esbuild/sunos-x64 | 0.21.5 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @esbuild/sunos-x64 | 0.25.12 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @esbuild/win32-arm64 | 0.21.5 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @esbuild/win32-arm64 | 0.25.12 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @esbuild/win32-ia32 | 0.21.5 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @esbuild/win32-ia32 | 0.25.12 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @esbuild/win32-x64 | 0.21.5 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @esbuild/win32-x64 | 0.25.12 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @eslint-community/eslint-utils | 4.9.1 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @eslint-community/regexpp | 4.12.2 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @eslint/eslintrc | 2.1.4 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @eslint/js | 8.57.1 | npm | yes | development/tooling dependency | development | MIT | present-in-baseline |
| @eslint/js | 9.39.4 | npm | yes | development/tooling dependency | development | MIT | present-in-baseline |
| @exodus/bytes | 1.15.1 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @exodus/schemasafe | 1.3.0 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @faker-js/faker | 7.6.0 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @formatjs/ecma402-abstract | 2.3.6 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @formatjs/fast-memoize | 2.2.7 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @formatjs/icu-messageformat-parser | 2.11.4 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @formatjs/icu-skeleton-parser | 1.8.16 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @formatjs/intl-localematcher | 0.6.2 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @gar/promise-retry | 1.0.3 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @gar/promisify | 1.1.3 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @hapi/address | 5.1.1 | npm | no | development/tooling dependency | development | BSD-3-Clause | present-in-baseline |
| @hapi/formula | 3.0.2 | npm | no | development/tooling dependency | development | BSD-3-Clause | present-in-baseline |
| @hapi/hoek | 11.0.7 | npm | no | development/tooling dependency | development | BSD-3-Clause | present-in-baseline |
| @hapi/pinpoint | 2.0.1 | npm | no | development/tooling dependency | development | BSD-3-Clause | present-in-baseline |
| @hapi/tlds | 1.1.6 | npm | no | development/tooling dependency | development | BSD-3-Clause | present-in-baseline |
| @hapi/topo | 6.0.2 | npm | no | development/tooling dependency | development | BSD-3-Clause | present-in-baseline |
| @headlessui/react | 1.7.19 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @hookstate/core | 4.0.2 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @humanwhocodes/config-array | 0.13.0 | npm | no | development/tooling dependency | development | Apache-2.0 | present-in-baseline |
| @humanwhocodes/module-importer | 1.0.1 | npm | no | development/tooling dependency | development | Apache-2.0 | present-in-baseline |
| @humanwhocodes/momoa | 2.0.4 | npm | no | development/tooling dependency | development | Apache-2.0 | present-in-baseline |
| @humanwhocodes/object-schema | 2.0.3 | npm | no | development/tooling dependency | development | BSD-3-Clause | present-in-baseline |
| @hyperjump/json | 0.1.0 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @hyperjump/json-pointer | 0.9.8 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @hyperjump/json-schema | 0.23.5 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @hyperjump/json-schema-core | 0.28.5 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @hyperjump/pact | 0.2.5 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @iconify/types | 2.0.0 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @iconify/utils | 3.1.3 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @inquirer/ansi | 1.0.2 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @inquirer/ansi | 2.0.7 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @inquirer/checkbox | 4.3.2 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @inquirer/confirm | 3.2.0 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @inquirer/confirm | 5.1.21 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @inquirer/confirm | 6.1.1 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @inquirer/core | 10.3.2 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @inquirer/core | 11.2.1 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @inquirer/core | 9.2.1 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @inquirer/editor | 4.2.23 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @inquirer/expand | 4.0.23 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @inquirer/external-editor | 1.0.3 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @inquirer/figures | 1.0.15 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @inquirer/figures | 2.0.7 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @inquirer/input | 2.3.0 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @inquirer/input | 4.3.1 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @inquirer/number | 3.0.23 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @inquirer/password | 4.0.23 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @inquirer/prompts | 7.10.1 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @inquirer/rawlist | 4.1.11 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @inquirer/search | 3.2.2 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @inquirer/select | 2.5.0 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @inquirer/select | 4.4.2 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @inquirer/type | 1.5.5 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @inquirer/type | 2.0.0 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @inquirer/type | 3.0.10 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @inquirer/type | 4.0.7 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @isaacs/cliui | 8.0.2 | npm | no | development/tooling dependency | development | ISC | present-in-baseline |
| @isaacs/cliui | 9.0.0 | npm | no | development/tooling dependency | development | BlueOak-1.0.0 | present-in-baseline |
| @isaacs/fs-minipass | 4.0.1 | npm | no | development/tooling dependency | development | ISC | present-in-baseline |
| @isaacs/string-locale-compare | 1.1.0 | npm | no | development/tooling dependency | development | ISC | present-in-baseline |
| @joshwooding/vite-plugin-react-docgen-typescript | 0.5.0 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @jridgewell/gen-mapping | 0.3.13 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @jridgewell/remapping | 2.3.5 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @jridgewell/resolve-uri | 3.1.2 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @jridgewell/source-map | 0.3.11 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @jridgewell/sourcemap-codec | 1.5.5 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @jridgewell/trace-mapping | 0.3.31 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @jridgewell/trace-mapping | 0.3.9 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @jsdevtools/ono | 7.1.3 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @jsep-plugin/assignment | 1.3.0 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @jsep-plugin/regex | 1.0.4 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |
| @jsep-plugin/ternary | 1.1.4 | npm | no | development/tooling dependency | development | MIT | present-in-baseline |

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
