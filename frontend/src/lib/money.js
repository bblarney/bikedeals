// One money formatter for the whole app. It was three identical copies until
// the cross-shop line needed a fourth: that line compares a floor price against
// the price printed beside it, and the comparison is only honest if both go
// through the same rounding.
export const money = (n) => `$${Math.round(n).toLocaleString('en-AU')}`
