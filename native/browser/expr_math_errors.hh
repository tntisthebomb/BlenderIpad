/* SPDX-License-Identifier: GPL-2.0-or-later */
/* Included inside namespace blender after the expression callback typedefs. */
static double op_div(double, double);
static double op_log2(double, double);
static double op_smoothstep(double, double, double);

class ExprMathErrors {
  enum { Divide = 1, Invalid = 2 };
  int errors_ = 0;

 public:
  ExprMathErrors()
  {
#ifndef __EMSCRIPTEN__
    feclearexcept(FE_ALL_EXCEPT);
#endif
  }
  bool ok() const { return status() == EXPR_PYLIKE_SUCCESS; }
  eExprPyLike_EvalStatus status() const
  {
#ifdef __EMSCRIPTEN__
    const int flags = errors_;
#else
    const int hardware = fetestexcept(FE_DIVBYZERO | FE_INVALID);
    const int flags = ((hardware & FE_DIVBYZERO) ? Divide : 0) |
                      ((hardware & FE_INVALID) ? Invalid : 0);
#endif
    return (flags & Invalid) ? EXPR_PYLIKE_MATH_ERROR :
           (flags & Divide) ? EXPR_PYLIKE_DIV_BY_ZERO : EXPR_PYLIKE_SUCCESS;
  }
  double call(UnaryOpFunc func, double a)
  {
    const double result = func(a);
#ifdef __EMSCRIPTEN__
    if (!std::isnan(a) && std::isnan(result)) errors_ |= Invalid;
    if ((func == UnaryOpFunc(log) || func == UnaryOpFunc(log10)) && a == 0.0) {
      errors_ |= Divide;
    }
#endif
    return result;
  }
  double call(BinaryOpFunc func, double a, double b)
  {
    const double result = func(a, b);
#ifdef __EMSCRIPTEN__
    if (!std::isnan(a) && !std::isnan(b) && std::isnan(result)) errors_ |= Invalid;
    if (func == op_div && std::isfinite(a) && a != 0.0 && b == 0.0) errors_ |= Divide;
    if (func == BinaryOpFunc(pow) && a == 0.0 && b < 0.0 && std::isfinite(b)) errors_ |= Divide;
    if (func == op_log2) {
      if (a < 0.0 || b < 0.0) errors_ |= Invalid;
      if (a == 0.0 || b == 0.0) errors_ |= Divide;
      const double numerator = log(a);
      if (b == 1.0 && std::isfinite(numerator) && numerator != 0.0) errors_ |= Divide;
    }
#endif
    return result;
  }
  double call(TernaryOpFunc func, double a, double b, double c)
  {
    const double result = func(a, b, c);
#ifdef __EMSCRIPTEN__
    if (!std::isnan(a) && !std::isnan(b) && !std::isnan(c) && std::isnan(result)) errors_ |= Invalid;
    // smoothstep clamps its intermediate infinity to a finite value; retain
    // the division error even when it is no longer visible in the result.
    if (func == op_smoothstep && b == a && std::isfinite(c - a) && c != a) errors_ |= Divide;
#endif
    return result;
  }
};
