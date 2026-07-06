<!--
Source file for GMATWiz challenge 7f ("AI card check").
License: authored-gmatwiz. ORIGINAL notes written for GMATWiz -- NOT copied from
any copyrighted textbook, prep book, or official GMAT material. This single file
is the one "real source" that card_check.py generates 50 candidate cards from.
Scope: GMAT Focus Quant, Problem Solving only (arithmetic + algebra).
-->

# GMATWiz Quant Notes, Chapter 3: Percents and Linear Equations

These are original study notes for two of the most-tested Problem Solving skills on
the GMAT Focus Quant section: working with **percents** and solving **linear
equations** (including the word problems that translate into them). Everything here
is solvable by hand, with no calculator, no figure, and no Data Sufficiency format.

---

## Part A. Percents

### A1. The three ways to read a percent

A percent is just a fraction out of 100. The single most useful fact is:

> "**p percent of a number N**" means **(p / 100) x N**.

- 25% of 80 = (25/100) x 80 = 0.25 x 80 = 20.
- 150% of 40 = 1.5 x 40 = 60 (percents can exceed 100%).
- To turn a percent into a decimal, divide by 100 (7% -> 0.07). To turn a decimal
  into a percent, multiply by 100 (0.4 -> 40%).

**"What percent"** questions reverse this. "12 is what percent of 48?" asks for
p in 12 = (p/100) x 48, so p = 100 x 12/48 = 25%. The pattern is
**part / whole x 100%**.

### A2. Percent increase and percent decrease

To change a quantity by a percent, multiply by a single factor:

- Increase by p%: multiply by **(1 + p/100)**. A 20% increase multiplies by 1.20.
- Decrease by p%: multiply by **(1 - p/100)**. A 30% decrease multiplies by 0.70.

Example: a $50 item marked up 20% costs 50 x 1.20 = $60. A $50 item discounted 30%
costs 50 x 0.70 = $35.

The **percent change** itself is
**(new value - old value) / (old value) x 100%**. If a salary goes from $40,000 to
$46,000, the percent increase is 6000/40000 x 100% = 15%.

### A3. Successive percent changes multiply (they do NOT add)

When two percent changes happen one after another, multiply the factors.

Example: a price rises 40%, then falls 25%. The combined factor is
1.40 x 0.75 = 1.05, so the final price is **105%** of the original -- a net 5%
increase, not the 15% you would get by subtracting. Order does not matter because
multiplication commutes: 1.40 x 0.75 = 0.75 x 1.40.

### A4. Reversing a percent (finding the original)

If you know the result and the percent applied, divide by the factor.

Example: after a 20% discount a book sells for $48. The sale price is 80% of the
original P, so 0.80 x P = 48 and **P = 48 / 0.80 = $60**. A common trap is to add
20% back to $48 (that gives $57.60, which is wrong) -- you must divide by 0.80.

### A5. Percent word-problem checklist

1. Identify the **whole** (the base the percent is taken of). The base can change
   between sentences -- read carefully.
2. Convert every percent to a decimal factor.
3. For a sequence of changes, multiply the factors.
4. To undo a change, divide by its factor.

---

## Part B. Linear Equations

### B1. What makes an equation linear

A linear equation has the variable only to the first power -- no x^2, no 1/x, no
square roots of x. Its graph is a straight line, and it has exactly one solution
(unless it is degenerate). The goal is always the same: **isolate the variable** by
undoing operations in reverse order.

### B2. Solving a one-variable linear equation

Do the same operation to both sides to keep the equation balanced.

Example: solve 4x + 7 = 2x + 19.

1. Subtract 2x from both sides: 2x + 7 = 19.
2. Subtract 7 from both sides: 2x = 12.
3. Divide both sides by 2: **x = 6**.

Always finish by substituting back: 4(6) + 7 = 31 and 2(6) + 19 = 31. They match, so
x = 6 is correct.

### B3. Translating words into a linear equation

Most GMAT algebra word problems are linear once you name a variable.

- "a number" -> let it be x.
- "three times the number" -> 3x.
- "5 more than the number" -> x + 5.
- "the number is" -> = (equals).

Example: a number added to three times itself equals 48. That is x + 3x = 48, so
4x = 48 and **x = 12**.

### B4. Systems of two linear equations

With two unknowns you need two equations. Two reliable methods:

- **Elimination:** add or subtract the equations to cancel one variable. Given
  3x - 2y = 12 and x + 2y = 8, adding them cancels y: 4x = 20, so x = 5. Then
  substitute to get y: 5 + 2y = 8, so y = 1.5.
- **Substitution:** solve one equation for a variable and plug it into the other.

### B5. Linear word-problem templates you will reuse

- **Mixture of counts and totals.** If adult tickets cost $8 and child tickets $5,
  and 20 tickets sold for $139, let a be adult tickets: 8a + 5(20 - a) = 139, so
  3a + 100 = 139 and a = 13.
- **Constant-rate travel (distance = rate x time).** A car covering 300 km in 5
  hours moves at 300/5 = 60 km/h, so in 8 hours it covers 60 x 8 = 480 km. This is
  a proportional (linear) relationship.
- **Simple interest.** Interest = principal x rate x time. On $1,500 at 6% per year
  for 4 years: 1500 x 0.06 x 4 = $360.

### B6. Common mistakes to avoid

1. Forgetting to apply an operation to **both** sides.
2. Sign errors when moving a term across the equals sign.
3. In word problems, leaving the answer as the variable when the question asks for a
   different quantity (e.g., solving for the child tickets when it asked for adult).
4. Not checking the answer by substitution -- a 10-second habit that catches most
   arithmetic slips.

---

## Quick reference

| Task | Rule |
| --- | --- |
| p% of N | (p/100) x N |
| what percent is part of whole | part/whole x 100% |
| increase by p% | multiply by (1 + p/100) |
| decrease by p% | multiply by (1 - p/100) |
| two successive changes | multiply the two factors |
| undo a percent change | divide by the factor |
| solve linear eq | isolate the variable, then check by substitution |
| system of two equations | eliminate or substitute |
| distance | rate x time |
| simple interest | principal x rate x time |

*End of Chapter 3. All examples and numbers above were written for GMATWiz and are
free to reuse under the project license.*
