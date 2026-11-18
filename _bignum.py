"""Big numbers for Infinideck: a float mantissa and an unlimited int exponent, so chips can reach numbers with a
million digits without overflowing (Python floats stop at about 1e308)."""
import math

# --- Settings ---
SHORT_NAMES = ((15, "Qd"), (12, "T"), (9, "B"), (6, "M"))     # 1e18 is "Qt" (handled below)
PRECISION = 17          # past this many digits apart, the smaller number can't change the bigger one
MAX_E = 10**15          # safety ceiling: numbers stop growing at 10^(10^15) instead of crashing


class Big:
    """value = m * 10**e, with 1 <= |m| < 10 (or m == 0)."""
    __slots__ = ("e", "m")

    def __init__(self, m=0.0, e=0):
        if isinstance(m, Big):
            self.m, self.e = m.m, m.e
            return
        self.m, self.e = float(m), int(e)
        self._norm()

    def _norm(self):
        m = self.m
        if m == 0 or math.isnan(m):
            self.m, self.e = 0.0, 0
            return
        if m in (math.inf, -math.inf):
            self.m, self.e = (9.999999 if m > 0 else -9.999999), MAX_E
            return
        shift = math.floor(math.log10(abs(m)))
        if shift:
            self.m = m / 10.0**shift
            self.e += shift
        if abs(self.m) >= 10:                     # rounding edge cases
            self.m /= 10
            self.e += 1
        elif abs(self.m) < 1:
            self.m *= 10
            self.e -= 1
        if self.e > MAX_E:
            self.m, self.e = (9.999999 if self.m > 0 else -9.999999), MAX_E
        elif self.e < -MAX_E:
            self.m, self.e = 0.0, 0

    # --- Making ---
    @staticmethod
    def of(x):
        return x if isinstance(x, Big) else Big(x)

    @staticmethod
    def from_log(log10_value, sign=1):
        """The number whose log10 is log10_value."""
        e = math.floor(log10_value)
        return Big(sign * 10.0 ** (log10_value - e), e)

    # --- Maths ---
    def __add__(self, other):
        o = Big.of(other)
        if self.m == 0:
            return Big(o)
        if o.m == 0:
            return Big(self)
        diff = self.e - o.e
        if diff > PRECISION:
            return Big(self)
        if diff < -PRECISION:
            return Big(o)
        if diff >= 0:
            return Big(self.m + o.m / 10.0**diff, self.e)
        return Big(self.m / 10.0**(-diff) + o.m, o.e)

    __radd__ = __add__

    def __neg__(self):
        return Big(-self.m, self.e)

    def __sub__(self, other):
        return self + (-Big.of(other))

    def __rsub__(self, other):
        return Big.of(other) - self

    def __mul__(self, other):
        o = Big.of(other)
        return Big(self.m * o.m, self.e + o.e)

    __rmul__ = __mul__

    def __truediv__(self, other):
        o = Big.of(other)
        if o.m == 0:
            raise ZeroDivisionError("Big division by zero")
        return Big(self.m / o.m, self.e - o.e)

    def __rtruediv__(self, other):
        return Big.of(other) / self

    def __pow__(self, p):
        if self.m == 0:
            return Big(0)
        if self.m < 0:
            raise ValueError("Big power of a negative number")
        return Big.from_log(self.log10() * float(p))

    def __abs__(self):
        return Big(abs(self.m), self.e)

    def log10(self):
        if self.m == 0:
            return -math.inf
        return self.e + math.log10(abs(self.m))

    def sign(self):
        return (self.m > 0) - (self.m < 0)

    def is_zero(self):
        return self.m == 0

    # --- Comparing ---
    def _cmp(self, other):
        o = Big.of(other)
        sa, sb = self.sign(), o.sign()
        if sa != sb:
            return (sa > sb) - (sa < sb)
        if sa == 0:
            return 0
        if self.e != o.e:
            r = 1 if self.e > o.e else -1
        else:
            r = (self.m > o.m) - (self.m < o.m)
            return r
        return r if sa > 0 else -r

    def __lt__(self, o):
        return self._cmp(o) < 0

    def __le__(self, o):
        return self._cmp(o) <= 0

    def __gt__(self, o):
        return self._cmp(o) > 0

    def __ge__(self, o):
        return self._cmp(o) >= 0

    def __eq__(self, o):
        try:
            return self._cmp(o) == 0
        except (TypeError, ValueError):
            return False

    def __hash__(self):
        return hash((round(self.m, 9), self.e))

    def __float__(self):
        if self.e > 307:
            return math.inf if self.m > 0 else -math.inf
        if self.e < -307:
            return 0.0
        return self.m * 10.0**self.e

    def __int__(self):
        if self.e > 300:
            raise OverflowError("too big for int")
        return int(float(self))

    def __bool__(self):
        return self.m != 0

    def __repr__(self):
        return f"Big({self.m!r}, {self.e})"

    # --- Saving ---
    def to_json(self):
        return [round(self.m, 15), self.e]

    @staticmethod
    def from_json(v):
        if isinstance(v, list) and len(v) == 2:
            return Big(v[0], v[1])
        return Big(v or 0)

    # --- Showing ---
    def digits(self):
        """How many digits the whole-number part has."""
        return max(1, self.e + 1) if self.m else 1

    def fmt(self, decimals=2):
        """1,234 / 12.5M / 3.2B / 4.1T / 1.5Qd / 2Qt / 1.23e21 (scientific past 999.99 Quintillion)."""
        if self.m == 0:
            return "0"
        neg = "-" if self.m < 0 else ""
        a = abs(self)
        if a.e < 6:
            v = float(a)
            if v >= 1000 or v == int(v):
                return f"{neg}{round(v):,}"
            if v >= 100:
                return f"{neg}{v:.0f}"
            return f"{neg}{v:.{1 if v >= 10 else 2}f}".rstrip("0").rstrip(".")
        if a.e < 21:
            if a.e >= 18:
                return f"{neg}{trim(float(a) / 1e18, decimals)}Qt"
            for power, name in SHORT_NAMES:
                if a.e >= power:
                    return f"{neg}{trim(float(a) / 10.0**power, decimals)}{name}"
        m = math.floor(a.m * 10**decimals) / 10**decimals        # round down: 9.9999 shows 9.99, never 10.00
        return f"{neg}{m:.{decimals}f}e{a.e:,}" if a.e >= 10**6 else f"{neg}{m:.{decimals}f}e{a.e}"

    def exact(self):
        """The full number with commas when it's small enough to read, else the scientific form."""
        if abs(self.e) < 16:
            return f"{round(float(self)):,}"
        return self.fmt(4)


def trim(v, decimals):
    """12.50 -> 12.5, 3.00 -> 3, but always 3 significant figures (100.4 -> 100)."""
    if v >= 100:
        text = f"{v:.0f}" if v < 999.5 else f"{min(v, 999.99):.2f}"     # never "1000M": that's 1B
    elif v >= 10:
        text = f"{v:.{max(0, decimals - 1)}f}"
    else:
        text = f"{v:.{decimals}f}"
    return text.rstrip("0").rstrip(".") if "." in text else text


ZERO = Big(0)
ONE = Big(1)
