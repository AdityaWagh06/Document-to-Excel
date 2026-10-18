import STR from '../constants/strings';

export function buildTableRows(payload) {
  const rows = [];
  const conf = payload?.confidence ?? 0;

  // Invoice Header Summary Rows
  rows.push({ id: 'vendor', section: 'Document Header', field: 'Vendor Name', value: payload?.vendor || '', confidence: conf });
  rows.push({ id: 'gstin', section: 'Document Header', field: 'GST Number (GSTIN)', value: payload?.gstin || '', confidence: conf });
  rows.push({ id: 'invoice_number', section: 'Document Header', field: 'Invoice Number', value: payload?.invoice_number || '', confidence: conf });
  rows.push({ id: 'date', section: 'Document Header', field: 'Invoice Date', value: payload?.date || '', confidence: conf });
  rows.push({ id: 'due_date', section: 'Document Header', field: 'Due Date', value: payload?.due_date || '', confidence: conf });
  
  // Tax & Amount Breakdown Rows
  rows.push({ id: 'subtotal', section: 'Tax & Amounts', field: 'Subtotal (₹)', value: payload?.subtotal || '0.00', confidence: conf });
  rows.push({ id: 'cgst', section: 'Tax & Amounts', field: 'CGST (₹)', value: payload?.cgst || '0.00', confidence: conf });
  rows.push({ id: 'sgst', section: 'Tax & Amounts', field: 'SGST (₹)', value: payload?.sgst || '0.00', confidence: conf });
  rows.push({ id: 'igst', section: 'Tax & Amounts', field: 'IGST (₹)', value: payload?.igst || '0.00', confidence: conf });
  rows.push({ id: 'tax_total', section: 'Tax & Amounts', field: 'Tax Total (₹)', value: payload?.tax_total || '0.00', confidence: conf });
  rows.push({ id: 'total', section: 'Tax & Amounts', field: 'Grand Total (₹)', value: payload?.total || '0.00', confidence: conf });

  // Line Items Rows
  (payload?.items || []).forEach((item, index) => {
    rows.push({
      id: `item-${index}`,
      section: 'Line Items',
      field: item?.description || `Line Item #${index + 1}`,
      value: item?.amount || '0.00',
      qty: item?.qty || '1',
      unit_price: item?.unit_price || '0.00',
      tax_rate: item?.tax_rate || '0%',
      hsn_sac: item?.hsn_sac || '',
      confidence: conf
    });
  });

  return rows;
}

export function rowsToPayload(rows, basePayload) {
  const items = [];
  let vendor = basePayload?.vendor || '';
  let gstin = basePayload?.gstin || '';
  let invoice_number = basePayload?.invoice_number || '';
  let date = basePayload?.date || '';
  let due_date = basePayload?.due_date || '';
  let subtotal = basePayload?.subtotal || '0.00';
  let cgst = basePayload?.cgst || '0.00';
  let sgst = basePayload?.sgst || '0.00';
  let igst = basePayload?.igst || '0.00';
  let tax_total = basePayload?.tax_total || '0.00';
  let total = basePayload?.total || '0.00';

  rows.forEach((row) => {
    if (row.id === 'vendor') vendor = row.value;
    if (row.id === 'gstin') gstin = row.value;
    if (row.id === 'invoice_number') invoice_number = row.value;
    if (row.id === 'date') date = row.value;
    if (row.id === 'due_date') due_date = row.value;

    if (row.id === 'subtotal') subtotal = row.value;
    if (row.id === 'cgst') cgst = row.value;
    if (row.id === 'sgst') sgst = row.value;
    if (row.id === 'igst') igst = row.value;
    if (row.id === 'tax_total') tax_total = row.value;
    if (row.id === 'total') total = row.value;

    if (row.section === 'Line Items') {
      items.push({
        description: row.field,
        amount: row.value,
        qty: row.qty || '1',
        unit_price: row.unit_price || row.value,
        tax_rate: row.tax_rate || '0%',
        hsn_sac: row.hsn_sac || '',
      });
    }
  });

  return {
    ...basePayload,
    vendor,
    gstin,
    invoice_number,
    date,
    due_date,
    subtotal,
    cgst,
    sgst,
    igst,
    tax_total,
    total,
    items
  };
}
