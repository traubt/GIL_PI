// =======================
// Date Utils (Global)
// =======================

// ISO (yyyy-mm-dd) -> dd/mm/yyyy
function isoToDmy(iso) {
    if (!iso) return '';
    const [y, m, d] = iso.split('-');
    if (!y || !m || !d) return '';
    return `${d.padStart(2,'0')}/${m.padStart(2,'0')}/${y}`;
}

// dd/mm/yyyy -> ISO (yyyy-mm-dd)
function dmyToIso(dmy) {
    if (!dmy) return '';
    const parts = dmy.split(/[./-]/);
    if (parts.length !== 3) return '';
    const [d, m, y] = parts;
    return `${y.padStart(4,'0')}-${m.padStart(2,'0')}-${d.padStart(2,'0')}`;
}

// Normalize anything -> dd/mm/yyyy (safe for tables)
function normalizeDate(val) {
    if (!val) return '';
    if (val.includes('-')) return isoToDmy(val);
    return val;
}
