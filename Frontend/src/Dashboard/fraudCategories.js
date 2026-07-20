// Maps the 13 unified-classifier category keys to readable chip labels.
// Keep in sync with RuleCategory in Backend/app/models/schemas.py.
export const CATEGORY_LABELS = {
  authority_impersonation: 'Authority Impersonation',
  credential_request: 'Credential Request',
  urgency_coercion: 'Urgency / Coercion',
  money_demand: 'Money Demand',
  reward_bait: 'Reward Bait',
  isolation_tactics: 'Isolation Tactics',
  otp_readout_request: 'OTP Readout Request',
  card_collection_request: 'Card Collection Request',
  relative_impersonation: 'Relative Impersonation',
  telecom_impersonation: 'Telecom Impersonation',
  extortion_threat: 'Extortion Threat',
  malicious_link_bait: 'Malicious Link Bait',
  malware_attachment_delivery: 'Malware Attachment Delivery',
};

export const categoryLabel = (key) => CATEGORY_LABELS[key] || key;

export const VERDICT_STYLES = {
  SAFE: 'bg-emerald-50 text-emerald-600',
  SUSPICIOUS: 'bg-amber-50 text-amber-600',
  SCAM: 'bg-red-50 text-red-600',
};
