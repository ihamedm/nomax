/** Iranian national ID checksum (10 digits, last digit is the check digit). */
export function isValidNationalId(nid: string): boolean {
  if (!/^\d{10}$/.test(nid)) return false;
  const digits = nid.split("").map(Number);
  const sum = digits.slice(0, 9).reduce((acc, d, i) => acc + d * (10 - i), 0);
  const remainder = sum % 11;
  return digits[9] === (remainder < 2 ? remainder : 11 - remainder);
}
