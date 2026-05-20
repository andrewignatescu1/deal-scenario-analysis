Interactive M&A Accretion/Dilution Model

A Python tool that evaluates whether a hypothetical acquisition is accretive or dilutive to the acquirer's earnings per share. It mirrors the logic used in investment banking and corporate development to screen potential deals.

When run, the program pulls live financial data for both the acquirer and target, including share price, shares outstanding, and latest annual net income. The user then enters deal parameters such as the acquisition premium, financing mix of cash, stock, and debt, tax rate, interest rate on new debt, expected synergies, and integration costs. Defaults are provided so the model can be run quickly or used for sensitivity testing.

The model combines both companies' net income, adds after tax synergies, subtracts after tax interest and amortization, and adjusts for dilution from newly issued shares. The resulting pro forma EPS is compared against the acquirer's standalone EPS to determine accretion or dilution.
To capture execution risk, the model automatically runs three scenarios. The base case reflects expected performance, the upside case assumes stronger synergies and lower costs, and the downside case reflects weaker execution. Each case flags whether the deal exceeds a defined dilution threshold.

The tool simplifies certain accounting details and is not a substitute for a full valuation, but it captures how acquisition economics shift under different pricing, financing, and execution assumptions
