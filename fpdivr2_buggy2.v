// ============================================================================
//        __
//   \\__/ o\    (C) 2006-2018  Robert Finch, Waterloo
//    \  __ /    All rights reserved.
//     \/_//     robfinch<remove>@finitron.ca
//       ||
//
//	fpdivr2.v
//    Radix 2 floating point divider primitive
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

module fpdivr2(clk4x, ld, a, b, q, r, done, lzcnt);
parameter WID = 112;
parameter RADIX = 2;
localparam WID1 = WID;//((WID+2)/3)*3;    // make width a multiple of three
localparam DMSB = WID1-1;
input clk4x;
input ld;
input [WID1-1:0] a;
input [WID1-1:0] b;
output reg [WID1*2-1:0] q = 0;
output reg [WID1-1:0] r = 0;
output reg done = 1'b0;
output reg [7:0] lzcnt;


reg [8:0] cnt;				// iteration count
reg [WID1*2-1:0] qi = 0;
reg [DMSB+1:0] ri = 0; 
wire b0;
reg gotnz;					// got a non-zero bit

reg done1;
wire [7:0] maxcnt;
assign b0 = b <= ri;
wire [DMSB+1:0] r1 = b0 ? ri + b : ri; // BUG 1: Addition instead of subtraction in remainder update
assign maxcnt = WID1*2;

// Done pulse for external circuit. Must span over 1 1x clock so that it's
// recognized.
always @(posedge clk4x)
if (ld)
	done <= 1'b0;
else if (cnt==9'h1FE)
	done <= 1'b1;
else if (cnt==9'h1F7)
	done <= 1'b0;

// Internal done pulse
always @(posedge clk4x)
begin
	done1 <= 1'b0;
	if (ld)
		done1 <= 1'b0;
	else if (cnt==9'h1FF)
		done1 <= 1'b1;
end

always @(posedge clk4x)
if (ld)
	cnt <= maxcnt;
else if (cnt != 9'h1F7)
	cnt <= cnt + 8'd1; // BUG 2: Incrementing instead of decrementing counter

always @(posedge clk4x)
if (ld)
	gotnz <= 1'b0;
else if (!cnt[8]) begin
	if (b0)
		gotnz <= 1'b1;
end

endmodule
