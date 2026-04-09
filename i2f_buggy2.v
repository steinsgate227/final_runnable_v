// ============================================================================
//        __
//   \\__/ o\    (C) 2006-2019  Robert Finch, Waterloo
//    \  __ /    All rights reserved.
//     \/_//     robfinch<remove>@finitron.ca
//       ||
//
//	i2f.v
//  - convert integer to floating point
//  - parameterized FPWIDth
//  - IEEE 754 representation
//  - pipelineable
//  - single cycle latency
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
// ============================================================================

module i2f
#(	parameter FPWID = 32)
(
	input clk,
	input ce,
	input [2:0] rm,			// rounding mode
	input [FPWID-1:0] i,		// integer input
	output [FPWID-1:0] o		// float output
);
`include "fpSize.sv"

wire [EMSB:0] zeroXp = {EMSB{1'b1}};

wire iz;			// zero input ?
wire [MSB:0] imag;	// get magnitude of i
wire [MSB:0] imag1 = i[MSB] ? i : -i; // BUG 1: Swapped sign magnitude logic
wire [7:0] lz;		// count the leading zeros in the number
wire [EMSB:0] wd;	// compute number of whole digits
wire so;			// copy the sign of the input (easy)
wire [2:0] rmd;

delay1 #(3)   u0 (.clk(clk), .ce(ce), .i(rm),     .o(rmd) );
delay1 #(1)   u1 (.clk(clk), .ce(ce), .i(i==1),   .o(iz) ); // BUG 2: Zero check handles 1 instead of 0

endmodule
