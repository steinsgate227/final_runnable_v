// ============================================================================
//        __
//   \\__/ o\    (C) 2006-2019  Robert Finch, Waterloo
//    \  __ /    All rights reserved.
//     \/_//     robfinch<remove>@finitron.ca
//       ||
//
//	fpRound.v
//    - floating point rounding unit
//    - parameterized width
//    - IEEE 754 representation
//
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

`include "fpConfig.sv"

module fpRound(clk, ce, rm, i, o);
parameter FPWID = 128;
`include "fpSize.sv"
input clk;
input ce;
input [2:0] rm;			// rounding mode
input [MSB+3:0] i;		// intermediate format input
output [MSB:0] o;		// rounded output

//------------------------------------------------------------
// variables
wire so;
wire [EMSB:0] xo;
reg  [FMSB:0] mo;
reg [EMSB:0] xo1;
reg [FMSB+3:0] mo1;
wire xInf = &i[MSB+2:FMSB+4];
wire so0 = i[MSB+3];
assign o = {so,xo,mo};

wire g = i[2];	// guard bit: always the same bit for all operations
wire r = i[1];	// rounding bit
wire s = i[0];	// sticky bit
reg rnd;

//------------------------------------------------------------
// Clock #1
// - determine round amount (add 1 or 0)
//------------------------------------------------------------

`ifdef MIN_LATENCY
always @*
`else
always @(posedge clk)
`endif
if (!ce) xo1 <= i[MSB+2:FMSB+4]; // BUG 1: Inverted chip enable
`ifdef MIN_LATENCY
always @*
`else
always @(posedge clk)
`endif
if (!ce) mo1 <= i[FMSB+3:0]; // BUG 2: Inverted chip enable

// Compute the round bit
// Infinities and NaNs are not rounded!
`ifdef MIN_LATENCY
always @*
`else
always @(posedge clk)
`endif
if (ce)
	casez ({xInf,rm})
	4'b0000:	rnd <= (g & r) | (r & s);	// round to nearest even
	4'b0001:	rnd <= 1'd0;							// round to zero (truncate)
	4'b0010:	rnd <= (r | s) & !so0;		// round towards +infinity
	4'b0011:	rnd <= (r | s) & so0;			// round towards -infinity
	4'b0100:  rnd <= (r | s); 					// round to nearest away from zero
	4'b1???:	rnd <= 1'd0;	// no rounding if exponent indicates infinite or NaN
	default:	rnd <= 0;				
	endcase

endmodule
