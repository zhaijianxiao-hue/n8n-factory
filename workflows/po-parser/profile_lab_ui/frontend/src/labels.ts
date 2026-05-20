export function approvalStateLabel(state: string | null | undefined): string {
  const labels: Record<string, string> = {
    draft: "草稿",
    generated: "已生成",
    evaluated: "已评测",
    submitted: "待管理员审核",
    changes_requested: "需修改",
    approved: "已批准",
    published: "已上线"
  };
  return state ? labels[state] ?? state : "草稿";
}

export function adminDecisionLabel(decision: string | null | undefined): string {
  const labels: Record<string, string> = {
    approved: "管理员已批准",
    rejected: "管理员已驳回"
  };
  return decision ? labels[decision] ?? decision : "暂无管理员结论";
}

export function notificationLabel(status: string | null | undefined): string {
  const labels: Record<string, string> = {
    "not sent": "未通知",
    sent: "已通知",
    failed: "通知失败",
    pending: "通知中"
  };
  return status ? labels[status] ?? status : "未通知";
}

export function issueReasonLabel(reason: string | null | undefined): string {
  const labels: Record<string, string> = {
    "business rule mismatch": "业务规则不一致",
    "field mismatch": "字段值不一致",
    "blocking mismatch": "阻断项不一致"
  };
  return reason ? labels[reason] ?? reason : "字段需要复核";
}

export function severityLabel(severity: string | null | undefined): string {
  const labels: Record<string, string> = {
    p0: "P0 阻断",
    p1: "P1 风险",
    warning: "提醒"
  };
  return severity ? labels[severity] ?? severity : "P0 阻断";
}

export interface FieldMeta {
  label: string;
  description: string;
}

const fieldLabels: Record<string, FieldMeta> = {
  customer_profile: { label: "客户档案", description: "当前样本匹配到的客户解析配置" },
  confidence: { label: "置信度", description: "模型对本次解析结果的整体信心" },
  warnings: { label: "风险提醒", description: "解析或业务规则检查产生的提醒" },
  status: { label: "解析状态", description: "本样本解析是否成功完成" },
  source_file: { label: "来源文件", description: "当前核对的原始PDF文件名" },
  "metadata.candidate_source": { label: "候选来源", description: "最终草稿采用的候选路径，例如视觉模型" },
  "metadata.model": { label: "模型名称", description: "生成本次候选结果的大模型" },
  "metadata.page_count": { label: "页数", description: "PDF总页数" },

  "header.customer_name": { label: "客户名称", description: "采购订单上的需方/客户名称" },
  "header.customer_code": { label: "客户代码", description: "系统内识别客户解析配置的代码" },
  "header.buyer_address": { label: "客户地址", description: "采购方地址或收货相关地址" },
  "header.supplier_id_at_customer": { label: "客户侧供应商编号", description: "客户系统中给供应商分配的编号" },
  "header.customer_contact_person": { label: "客户联系人", description: "订单上的需方联系人" },
  "header.customer_contact_phone": { label: "客户联系电话", description: "需方联系人电话" },
  "header.customer_contact_fax": { label: "客户传真", description: "需方传真号码" },
  "header.customer_contact_email": { label: "客户邮箱", description: "需方联系人邮箱" },
  "header.supplier_name": { label: "供应商名称", description: "订单上的供方名称" },
  "header.supplier_contact_person": { label: "供应商联系人", description: "供方联系人" },
  "header.supplier_address": { label: "供应商地址", description: "供方地址" },
  "header.po_number": { label: "采购订单号", description: "PO单据编号" },
  "header.po_date": { label: "订单日期", description: "采购订单签发或下单日期" },
  "header.currency": { label: "币种", description: "订单金额使用的货币" },
  "header.total_amount": { label: "订单总金额", description: "订单抬头或合计处的总金额" },
  "header.total_qty": { label: "订单总数量", description: "订单抬头或合计处的总数量" },
  "header.payment_terms": { label: "付款条件", description: "客户约定的付款期限或方式" },
  "header.delivery_terms": { label: "交货条款", description: "贸易条款、交货地或配送条件" },
  "header.shipment_mode": { label: "运输方式", description: "空运、海运、快递等运输方式" },
  "header.delivery_tolerance_positive_pct": { label: "正交货容差", description: "允许多交比例" },
  "header.delivery_tolerance_negative_pct": { label: "负交货容差", description: "允许少交比例" },
  "header.delivery_tolerance_raw": { label: "交货容差原文", description: "订单上关于交货容差的原始表述" },
  "header.blanket_order_note": { label: "框架订单备注", description: "框架订单数量、剩余数量等说明" },
  "header.production_note": { label: "生产备注", description: "客户对生产、库存或交期调整的说明" },
  "header.packaging_note": { label: "包装备注", description: "客户对包装、分批交付等要求" },

  "items[].line_no": { label: "行号", description: "PO明细行号" },
  "items[].customer_material": { label: "客户物料号", description: "客户侧物料编码" },
  "items[].material_description": { label: "客户物料描述", description: "客户订单上的存货名称、型号规格或物料描述" },
  "items[].qty": { label: "数量", description: "本行采购数量" },
  "items[].unit": { label: "单位", description: "数量单位" },
  "items[].delivery_date": { label: "计划到货日期", description: "客户要求到货或交付日期" },
  "items[].unit_price": { label: "含税单价", description: "本行含税单价" },
  "items[].price_basis_qty": { label: "计价基数", description: "价格对应的数量基数，例如每100件" },
  "items[].amount": { label: "价税合计", description: "本行金额合计" },
  "items[].currency": { label: "币种", description: "本行金额币种" },
  "items[].order_no": { label: "订单号", description: "客户关联订单号" },
  "items[].order_position": { label: "订单位置", description: "客户关联订单位置号" },
  "items[].article_raw": { label: "客户Article", description: "客户订单上的Article或物料引用" },
  "items[].remarks": { label: "明细备注", description: "本行补充说明" }
};

export function fieldMeta(path: string): FieldMeta {
  const normalized = path.replace(/\[\d+\]/g, "[]");
  const direct = fieldLabels[path] ?? fieldLabels[normalized];
  if (direct) {
    return direct;
  }

  const parts = path.split(".");
  const fallbackLabel = parts[parts.length - 1]?.replace(/_/g, " ").replace(/\[\d+\]/g, "") || path;
  return {
    label: fallbackLabel,
    description: "暂无字段说明，可按业务需要补充"
  };
}
