# License

## Bismut Compiler — GPLv3 with Runtime Library Exception

Copyright (c) 2026 Michael Binder

### Compiler License (GPLv3)

The Bismut compiler (all source code in this repository) is free software:
you can redistribute it and/or modify it under the terms of the
**GNU General Public License v3.0** as published by the Free Software
Foundation.

This means:

- You **may** use, study, modify, and distribute the compiler.
- Any **fork or derivative work** of the compiler must also be released
  under GPLv3 (or a compatible license) — it must remain open source.
- Forks and derivative works **must** give appropriate credit to the
  original project and indicate what changes were made.
- You **may not** create a closed-source version of the compiler and
  distribute or sell it as your own product.

The full text of the GPLv3 is available at:
<https://www.gnu.org/licenses/gpl-3.0.html>

### Runtime Library Exception

As a special exception, the runtime support code (`rt/` headers),
standard library C sources (`libs/`), and standard library Bismut
modules (`modules/`) that are compiled and linked into programs built
by the Bismut compiler do **not** cause the resulting compiled program
to be covered by the GPLv3. You may distribute such compiled programs
under any terms you choose, with no obligation to release your source
code.

This exception applies only to the **output** of the compiler (compiled
programs and their linked runtime). It does **not** apply to the
compiler itself or to modifications of the compiler.

### In Plain Terms

| What you want to do | Allowed? |
|---|---|
| Use the Bismut compiler to build commercial, closed-source software | **Yes** |
| Sell programs you wrote in Bismut | **Yes** |
| Use the compiler in a commercial development workflow | **Yes** |
| Fork the compiler and keep your fork open source | **Yes** |
| Fork the compiler and make it closed source | **No** |
| Redistribute the compiler without crediting the original project | **No** |
| Rebrand and sell the compiler as your own product | **No** |
| Take runtime/libs/modules source code and use it in a non-Bismut project | **No** (GPLv3 applies) |
| Rebrand or redistribute the runtime/libs/modules as your own work | **No** (GPLv3 applies) |
| Import standard library modules in your Bismut project | **Yes** (that's what they're for) |
| Distribute programs compiled with the Bismut compiler | **Yes** (exception applies) |
