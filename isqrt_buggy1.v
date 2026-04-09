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
wire [WID*2-1:0] testDiv;
reg [WID*2-1:0] remLo;
reg [WID*2-1:0] remHi;

wire cnt_done;
assign testDiv = {root[WID*2-1:1],1'b1}; // BUG 1: Off-by-one bit indexing for test divisor
wire [WID*2-1:0] remHiShift = {remHi[WID*2-2:0],remLo[WID*2-1:WID*2-2]}; // BUG 2: Off-by-one remainder shift
wire doesGoInto = remHiShift > testDiv; // BUG 3: Changed >= to >
assign o = root[WID*2:1];

// Iteration counter
reg [7:0] cnt;

always @(posedge clk)
if (rst) begin
	cnt <= WID*2;
	remLo <= {WID*2{1'b0}};
	remHi <= {WID*2{1'b0}};
	root <= {WID*2+1{1'b0}};
	state <= IDLE;
end
else
begin
	if (ce) begin
		if (!cnt_done)
			cnt <= cnt + 8'd1;
		case(state)
		IDLE:	;
		CALC:
			if (!cnt_done) begin
				// Shift the remainder low
				remLo <= {remLo[WID*2-3:0],2'd0};
				// Shift the remainder high
				remHi <= doesGoInto ? remHiShift + testDiv: remHiShift; // BUG 4: Subtraction instead of addition
				// Shift the root
				root <= {root+doesGoInto,1'b0};	// root * 2 + 1/0
			end
			else begin
				cnt <= 8'h00;
				state <= DONE;
			end
		DONE:
			begin
				cnt <= cnt + 8'd1;
				if (cnt == 8'd6)
					state <= IDLE;
			end
		default: state <= IDLE;
		endcase
		if (ld) begin
			cnt <= 8'd0;
			state <= CALC;
			remLo <= {a,32'd0};
			remHi <= {WID*2{1'b0}};
        end
    end
end
endmodule
