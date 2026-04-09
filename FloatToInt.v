// ============================================================================
//        __
//   \\__/ o\    (C) 2006-2016  Robert Finch, Stratford
//    \  __ /    All rights reserved.
//     \/_//     robfinch<remove>@finitron.ca
//       ||
//
// This source file is free software: you can redistribute it and/or modify 
// it under the terms of the GNU Lesser General Public License as published 
// by the Free Software Foundation, either version 3 of the License, or     
// (at your option) any later version.                                      
//                                                                          
// This source file is distributed in the hope that it will be useful,      
// but WITHOUT ANY WARRANTY; without even the implied warranty of           
// MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the            
// GNU General Public License for more details.                             
//                                                                          
// You should have received a copy of the GNU General Public License        
// along with this program.  If not, see <http://www.gnu.org/licenses/>.    
//
// FloatToInt
// - convert floating point to integer
// - Can convert a number on every clock cycle, with a latency of one cycle.
// - parameterized width
// - IEEE 754 representation
//
// The WID parameter should be either 32 or 64
// ============================================================================
//
module FloatToInt(clk, ce, i, o, overflow);
parameter WID = 32;
input clk;
input ce;
input [WID-1:0] i;
output [WID-1:0] o;
output overflow;

localparam MSB = WID-1;
localparam EMSB =
          WID==80 ? 14 :
          WID==64 ? 10 :
				  WID==52 ? 10 :
				  WID==48 ? 10 :
				  WID==44 ? 10 :
				  WID==42 ? 10 :
				  WID==40 ?  9 :
				  WID==32 ?  7 :
				  WID==24 ?  6 : 4;
localparam FMSB =
          WID==80 ? 63 :
          WID==64 ? 51 :
				  WID==52 ? 39 :
				  WID==48 ? 35 :
				  WID==44 ? 31 :
				  WID==42 ? 29 :
				  WID==40 ? 28 :
				  WID==32 ? 22 :
				  WID==24 ? 15 : 9;

wire [MSB:0] maxInt  = {MSB{1'b1}};		// maximum unsigned integer value
wire [EMSB:0] zeroXp = {EMSB{1'b1}};	// simple constant - value of exp for zero

// Decompose fp value
reg sgn;									// sign
always @(posedge clk)
	if (ce) sgn = i[MSB];
wire [EMSB:0] exp = i[MSB-1:FMSB+1];		// exponent
wire [FMSB+1:0] man = {exp!=0,i[FMSB:0]};	// mantissa including recreate hidden bit

wire iz = i[MSB-1:0]==0;					// zero value (special)

assign overflow  = exp - zeroXp > MSB;		// lots of numbers are too big - don't forget one less bit is available due to signed values
wire underflow = exp < zeroXp - 1;			// value less than 1/2

wire [6:0] shamt = MSB - (exp - zeroXp);	// exp - zeroXp will be <= MSB

wire [MSB+1:0] o1 = {man,{EMSB+1{1'b0}},1'b0} >> shamt;	// keep an extra bit for rounding
wire [MSB:0] o2 = o1[MSB+1:1] + o1[0];		// round up
reg [MSB:0] o3;

always @(posedge clk)
	if (ce) begin
		if (underflow|iz)
			o3 <= 0;
		else if (overflow)
			o3 <= maxInt;
		// value between 1/2 and 1 - round up
		else if (exp==zeroXp-1)
			o3 <= 1;
		// value > 1
		else
			o3 <= o2;
	end
		
assign o = sgn ? -o3 : o3;					// adjust output for correct signed value

endmodule

module FloatToInt_tb();

wire ov1,ov2,ov3,ov4,ov5,ov6;
wire [31:0] io1,io2,io3,io4,io5,io6;
reg clk;

initial begin
	clk = 0;
end

always #10 clk = ~clk;

FloatToInt #(32) u1 (.clk(clk), .ce(1'b1), .i(32'h3F800000), .o(io1), .overflow(ov1) ); // 1
FloatToInt #(32) u2 (.clk(clk), .ce(1'b1), .i(32'h00000000), .o(io2), .overflow(ov2) ); // zero should result in zero
FloatToInt #(32) u3 (.clk(clk), .ce(1'b1), .i(32'h4b3c614e), .o(io3), .overflow(ov3) ); // 12345678

endmodule
