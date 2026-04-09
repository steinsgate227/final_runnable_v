`timescale 1ns / 1ps
// ============================================================================
//        __
//   \\__/ o\    (C) 2010-2019  Robert Finch, Waterloo
//    \  __ /    All rights reserved.
//     \/_//     robfinch<remove>@finitron.ca
//       ||
//
//	isqrt.v
//	- integer square root
//  - uses the standard long form calc.
//	- geared towards use in an floating point unit
//	- calculates to WID fractional precision (double width output)
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

module isqrt(rst, clk, ce, ld, a, o, done);
parameter WID = 32;
localparam MSB = WID-1;
parameter IDLE=3'd0;
parameter CALC=3'd1;
parameter DONE=3'd2;
input rst;
input clk;
input ce;
input ld;
input [MSB:0] a;
output [WID*2-1:0] o;
output done;

reg [2:0] state;
reg [WID*2:0] root;

always @(posedge clk)
if (!rst) begin // BUG 1: Inverted reset
	state <= IDLE;
end
else
begin
	if (!ce) begin // BUG 2: Inverted chip enable
		case(state)
        // ...state logic partially omitted...
        endcase
    end
end
endmodule
