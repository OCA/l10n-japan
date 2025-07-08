This module provides the ability to configure tax rounding methods in invoices and other
business documents such as sales orders and purchase orders. Supported methods include
Half-up (Default), Round-up, and Round-down.

Only 'exclusive' taxes are supported, and the rounding behavior is limited to the 
`round_globally` option of the `tax_calculation_rounding_method`. It assumes that the 
`round_per_line` method is not used in Japan.
