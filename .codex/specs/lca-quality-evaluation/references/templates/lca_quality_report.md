---
template_kind: lca_quality_report
template_version: "2.1"
review_id: "<review_id>"
rubric_version: "<rubric_version>"
---

# LCA 质量评估报告

> 本报告是项目质量治理评价，不构成 ISO 认证、正式符合性认证或独立关键审查。

## 1. 评估摘要

记录总体状态、允许用途、评价时间、评估器和结论理由。

## 2. 适用性声明

| 项目 | 结论 | 证据/理由 |
| :--- | :--- | :--- |
| 研究类型 | `<value>` | `<evidence>` |

## 3. 标准依据

| 标准 | 版本 | 原文路径 | SHA-256 | 定位 |
| :--- | :--- | :--- | :--- | :--- |
| `<id>` | `<edition>` | `<path>` | `<sha256>` | `<locator>` |

## 4. 输入证据与产物覆盖

workflow manifest 必须为 `completed`；ProductSystem 模型图必须状态成功、节点非空且不存在断链或断连节点。

| Artifact ID | 类型 | 路径 | 文件状态 | Schema 状态 | SHA-256 | 说明 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `<id>` | `<kind>` | `<path>` | `<status>` | `<schema-status>` | `<sha256>` | `<details>` |

## 5. 维度汇总

| 维度 | 短板等级 | 0 | 1 | 2 | 3 | 适用项数 |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: |
| `<dimension>` | `<level>` | `<n>` | `<n>` | `<n>` | `<n>` | `<n>` |

## 6. 逐项评分

| ID | 检查项 | 适用性 | 门禁 | 等级 | 标准引用 | 证据 | 发现/缺口 | Issue | 责任建议 | 复审条件 |
| :--- | :--- | :--- | :--- | ---: | :--- | :--- | :--- | :--- | :--- | :--- |
| `<criterion-id>` | `<title>` | `<applicability>` | `<gate>` | `<level>` | `<standard-ref>` | `<evidence>` | `<finding>` | `<issue-id>` | `<owner>` | `<condition>` |

## 7. 问题与修正要求

| Issue ID | 严重度 | 检查项 | 状态 | 发现 | 修正要求 | 证据 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `<issue-id>` | `<severity>` | `<criterion-id>` | `<status>` | `<finding>` | `<action>` | `<evidence>` |

## 8. 限制与建议

列出允许使用边界、评估器限制和建议。Markdown 内容必须与 `lca_quality_score.json` 一致。
