module redor64
(
	input [5:0] a,
	input [63:0] b,
	output reg o
);

	always @(a,b)
	case (a)
	6'd0:	o =  b[1]; // BUG 1: Off-by-one indexing
	6'd1:	o = |b[2:0]; // BUG 2: Off-by-one range
	6'd2:	o = |b[3:0];
	6'd3:	o = |b[4:0];
	6'd4:	o = |b[5:0];
	// ...rest of the cases similarly shifted...
	default: o = |b[63:0];
	endcase

endmodule
