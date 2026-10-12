// Emscripten does not automatically copy Node's process.env into C getenv().
// Restrict this explicitly named core-validation profile to supported C-locale
// operations. The complete unthreaded diagnostic still runs these four cases.
Module['preRun'] ??= [];
Module['preRun'].push(function () {
  ENV['GTEST_FILTER'] = '*-chrono_test.weekday:chrono_test.year_month_day:unicode_test.legacy_locale:locale_test.chrono_weekday';
});
