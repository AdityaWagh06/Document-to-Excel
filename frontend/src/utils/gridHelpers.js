
export function buildTableRows(payload) {
  const rows = [];
  const conf = payload?.confidence ?? 0;

  // Invoice Header Summary Rows
  rows.push({ id: 'vendor', section: 'Document Header', field: 'Vendor Name', value: payload?.vendor || '', confidence: conf });
  rows.push({ id: 'gstin', section: 'Document Header', field: payload?.currency && payload.currency !== 'INR' ? 'Tax ID / GSTIN' : 'GST Number (GSTIN)', value: payload?.gstin || '', confidence: conf });
  rows.push({ id: 'invoice_number', section: 'Document Header', field: 'Invoice Number', value: payload?.invoice_number || '', confidence: conf });
  rows.push({ id: 'date', section: 'Document Header', field: 'Invoice Date', value: payload?.date || '', confidence: conf });
  rows.push({ id: 'due_date', section: 'Document Header', field: 'Due Date', value: payload?.due_date || '', confidence: conf });
  
  rows.push({ id: 'currency', section: 'Document Header', field: 'Currency (ISO code, e.g. INR, USD)', value: payload?.currency || '', confidence: conf });

  // Tax & Amount Breakdown Rows (amounts are in the document's own currency)
  const cur = payload?.currency ? ` (${payload.currency})` : '';
  const amountRow = (id, label) =>
    rows.push({ id, section: 'Tax & Amounts', field: `${label}${cur}`, value: payload?.[id] || '0.00', confidence: conf });
  amountRow('subtotal', 'Subtotal');
  const isIndian = !payload?.currency || payload.currency === 'INR' || payload?.gstin;
  ['cgst', 'sgst', 'igst'].forEach((id) => {
    if (isIndian || Number(payload?.[id] || 0) !== 0) amountRow(id, id.toUpperCase());
  });
  amountRow('tax_total', 'Tax total');
  amountRow('discount', 'Discount');
  amountRow('other_charges', 'Other charges (tip, delivery…)');
  amountRow('total', 'Grand total');

  // Line Items Rows
  (payload?.items || []).forEach((item, index) => {
    rows.push({
      id: `item-${index}`,
      section: 'Line Items',
      field: item?.description || `Line Item #${index + 1}`,
      value: item?.amount || '0.00',
      qty: item?.qty || '1',
      // Receipts often print no rate; leave it blank rather than showing a fake 0.00
      unit_price: Number(item?.unit_price) ? item.unit_price : '',
      tax_rate: item?.tax_rate || '0%',
      tax_amount: item?.tax_amount || '0.00',
      hsn_sac: item?.hsn_sac || '',
      confidence: conf
    });
  });

  return rows;
}

const HEADER_FIELDS = ['vendor', 'gstin', 'invoice_number', 'date', 'due_date', 'currency'];
const AMOUNT_FIELDS = ['subtotal', 'cgst', 'sgst', 'igst', 'tax_total', 'discount', 'other_charges', 'total'];

export function rowsToPayload(rows, basePayload) {
  const result = { ...basePayload };
  const items = [];

  rows.forEach((row) => {
    if (HEADER_FIELDS.includes(row.id)) result[row.id] = row.id === 'currency' ? String(row.value || '').trim().toUpperCase() : row.value;
    if (AMOUNT_FIELDS.includes(row.id)) result[row.id] = row.value;

    if (row.section === 'Line Items') {
      items.push({
        description: row.field,
        amount: row.value,
        qty: row.qty || '1',
        unit_price: row.unit_price || (Number(row.qty || 1) === 1 ? row.value : ''),
        tax_rate: row.tax_rate || '0%',
        tax_amount: row.tax_amount || '0.00',
        hsn_sac: row.hsn_sac || '',
      });
    }
  });

  return { ...result, items };
}
