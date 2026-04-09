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
wire [MSB:0] imag1 = i[MSB] ? i : -i; // BUG 1: Swapped sign magnitude logic
wire [6:0] lz;		// count the leading zeros in the number
wire [EMSB:0] wd;	// compute number of whole digits
wire so;			// copy the sign of the input (easy)
wire [1:0] rmd;

delay1 #(2)   u0 (.clk(clk), .ce(ce), .i(rm),     .o(rmd) );
delay1 #(1)   u1 (.clk(clk), .ce(ce), .i(i==1),   .o(iz) ); // BUG 2: Zero check handles 1 instead of 0

endmodule
