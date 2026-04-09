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
// IntToFloat
// - Integer to floating point conversion
// - Can convert a number on every clock cycle, with a latency of one cycle.
// - parameterized width
// - IEEE 754 representation
//
// The WID parameter should be either 32 or 64
// ============================================================================
//
module IntToFloat(clk, ce, rm, i, o);
parameter WID = 32;
input clk;
input ce;
input [2:0] rm;			// rounding mode
input [WID-1:0] i;		// integer input
output [WID-1:0] o;		// float output

localparam MSB = WID-1;
localparam EMSB = WID==64 ? 10 : 7;
localparam FMSB = WID==64 ? 51 : 22;

wire [EMSB:0] zeroXp = {EMSB{1'b1}};

wire iz;			// zero input ?
wire [MSB:0] imag;	// get magnitude of i
wire [MSB:0] imag1 = i[MSB] ? -i : i;
wire [6:0] lz;		// count the leading zeros in the number
wire [EMSB:0] wd;	// compute number of whole digits
wire so;			// copy the sign of the input (easy)
wire [1:0] rmd;

delay1 #(2)   u0 (.clk(clk), .ce(ce), .i(rm),     .o(rmd) );
delay1 #(1)   u1 (.clk(clk), .ce(ce), .i(i==0),   .o(iz) );
delay1 #(WID) u2 (.clk(clk), .ce(ce), .i(imag1),  .o(imag) );
delay1 #(1)   u3 (.clk(clk), .ce(ce), .i(i[MSB]), .o(so) );
generate 
if (WID==64) begin
cntlz64Reg    u4 (.clk(clk), .ce(ce), .i(imag1), .o(lz) );
end else begin
cntlz32Reg    u4 (.clk(clk), .ce(ce), .i(imag1), .o(lz) );
assign lz[6]=1'b0;
end
endgenerate

assign wd = zeroXp - 1 + WID - lz;	// constant except for lz

wire [EMSB:0] xo = iz ? 0 : wd;
wire [MSB:0] simag = imag << lz;		// left align number

wire g =  simag[EMSB+2];	// guard bit (lsb)
wire r =  simag[EMSB+1];	// rounding bit
wire s = |simag[EMSB:0];	// "sticky" bit
reg rnd;

// Compute the round bit
always @(rmd,g,r,s,so)
	case (rmd)
	3'd0:	rnd = (g & r) | (r & s);	// round to nearest even
	3'd1:	rnd = 0;					// round to zero (truncate)
	3'd2:	rnd = (r | s) & !so;		// round towards +infinity
	3'd3:	rnd = (r | s) & so;			// round towards -infinity
	// The following reserved for additional round mode
	default: rnd = 0;					// round to zero (truncate)
	endcase

// "hide" the leading one bit = MSB-1
// round the result
wire [FMSB:0] mo = simag[MSB-1:EMSB+1]+rnd;

assign o = {so,xo,mo};

endmodule


module IntToFloat_tb();

reg clk;
reg [7:0] cnt;
wire [31:0] fo1,fo2,fo3,fo4,fo5,fo6;
initial begin
clk = 1'b0;
cnt = 0;
end
always #10 clk=!clk;

always @(posedge clk)
	cnt = cnt + 1;

// Some test cases
IntToFloat #(32) u1 (.clk(clk), .ce(1), .rm(2'd0), .i(0),        .o(fo1) ); // zero should return zero (INT min)
IntToFloat #(32) u2 (.clk(clk), .ce(1), .rm(2'd0), .i(1),        .o(fo2) );
IntToFloat #(32) u3 (.clk(clk), .ce(1), .rm(2'd0), .i(-1),       .o(fo3) ); // ensure negative flows through
IntToFloat #(32) u4 (.clk(clk), .ce(1), .rm(2'd0), .i(16777226), .o(fo4) );
IntToFloat #(32) u5 (.clk(clk), .ce(1), .rm(2'd0), .i(32'h7FFFFFFF), .o(fo5) ); // INT max
IntToFloat #(32) u6 (.clk(clk), .ce(1), .rm(2'd0), .i(32'h80000000), .o(fo6) ); // INT max negative

endmodule
