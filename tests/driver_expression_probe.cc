/* SPDX-License-Identifier: GPL-2.0-or-later */
#include "BLI_expr_pylike_eval.h"
#include "CLG_log.h"
#include <cstdio>
#include <cmath>

using namespace blender;
struct Case { const char *text; double x; eExprPyLike_EvalStatus status; };
int main()
{
  CLG_init();
  const Case cases[] = {
    {"2+3",0,EXPR_PYLIKE_SUCCESS}, {"1/x",2,EXPR_PYLIKE_SUCCESS},
    {"0/0",0,EXPR_PYLIKE_MATH_ERROR}, {"1/0",0,EXPR_PYLIKE_DIV_BY_ZERO},
    {"1/x",0,EXPR_PYLIKE_DIV_BY_ZERO}, {"sqrt(-1)",0,EXPR_PYLIKE_MATH_ERROR},
    {"sqrt(x)",-1,EXPR_PYLIKE_MATH_ERROR}, {"sqrt(x)",0,EXPR_PYLIKE_SUCCESS},
    {"pow(-1,0.5)",0,EXPR_PYLIKE_MATH_ERROR}, {"pow(-1,x)",0.5,EXPR_PYLIKE_MATH_ERROR},
    {"sqrt(x)+1/max(0,x)",-1,EXPR_PYLIKE_MATH_ERROR},
    {"sqrt(x)+1/max(0,x)",0,EXPR_PYLIKE_DIV_BY_ZERO},
    {"sqrt(x)+1/max(0,x)",1,EXPR_PYLIKE_SUCCESS},
    {"log(0)",0,EXPR_PYLIKE_DIV_BY_ZERO}, {"log(-1)",0,EXPR_PYLIKE_MATH_ERROR},
    {"log(8,1)",0,EXPR_PYLIKE_DIV_BY_ZERO}, {"log(1,1)",0,EXPR_PYLIKE_MATH_ERROR},
    {"log(1,0)",0,EXPR_PYLIKE_DIV_BY_ZERO}, {"log(0,0)",0,EXPR_PYLIKE_MATH_ERROR},
    {"pow(0,-1)",0,EXPR_PYLIKE_DIV_BY_ZERO}, {"fmod(1,0)",0,EXPR_PYLIKE_MATH_ERROR},
    {"asin(2)",0,EXPR_PYLIKE_MATH_ERROR}, {"acos(2)",0,EXPR_PYLIKE_MATH_ERROR},
    {"smoothstep(0,0,1)",0,EXPR_PYLIKE_DIV_BY_ZERO},
    {"smoothstep(0,0,0)",0,EXPR_PYLIKE_MATH_ERROR},
    {"min(log(0),1)",0,EXPR_PYLIKE_DIV_BY_ZERO},
    {"sqrt(-1) if False else 7",0,EXPR_PYLIKE_SUCCESS},
    {"True or sqrt(-1)",0,EXPR_PYLIKE_SUCCESS},
    {"False and sqrt(-1)",0,EXPR_PYLIKE_SUCCESS},
    {"1e308*1e308",0,EXPR_PYLIKE_SUCCESS}, {"exp(1000)",0,EXPR_PYLIKE_SUCCESS},
    {"0*exp(1000)",0,EXPR_PYLIKE_MATH_ERROR},
    {"x",INFINITY,EXPR_PYLIKE_SUCCESS}, {"x-x",INFINITY,EXPR_PYLIKE_MATH_ERROR},
    {"x*0",INFINITY,EXPR_PYLIKE_MATH_ERROR},
  };
  const char *parameters[] = {"x"};
  for (const auto &test : cases) {
    auto *parsed = BLI_expr_pylike_parse(test.text, parameters, 1);
    double value = 0;
    const auto status = BLI_expr_pylike_eval(parsed, &test.x, 1, &value);
    if (status != test.status) {
      fprintf(stderr,"FAIL: %s at x=%g returned status %d, expected %d\n",test.text,test.x,int(status),int(test.status));
      return 1;
    }
    if (test.status != EXPR_PYLIKE_SUCCESS && BLI_expr_pylike_is_constant(parsed)) {
      fprintf(stderr,"FAIL: invalid operation was incorrectly constant-folded: %s\n",test.text);
      return 1;
    }
    BLI_expr_pylike_free(parsed);
  }
  CLG_exit();
  printf("PASS: %zu actual Blender driver-expression cases, domain errors, error precedence, masked intermediate errors, short-circuiting, constant folding and overflow behavior.\n",sizeof(cases)/sizeof(cases[0]));
  return 0;
}
