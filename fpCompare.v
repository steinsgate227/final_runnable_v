// ============================================================================
//        __
//   \\__/ o\    (C) 2007-2016  Robert Finch, Stratford
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
//	fpCompare.v
//  - floating point comparison unit
//  - parameterized width
//  - IEEE 754 representation
//
// Compares two fgloating point numbers and returns a status output.
// Bit:
// 0:   1 = equal, 0=not equal
// 1:   1 = less than,
// 2:   1 = magnitude less than
// 3:   1 = unordered (nan in compare)
// ============================================================================
//
module fpCompare(a, b, o, nanx);
parameter WID = 32;
localparam MSB = WID-1;
localparam EMSB = WID==80 ? 14 :
                  WID==64 ? 10 :
				  WID==52 ? 10 :
				  WID==48 ? 10 :
				  WID==44 ? 10 :
				  WID==42 ? 10 :
				  WID==40 ?  9 :
				  WID==32 ?  7 :
				  WID==24 ?  6 : 4;
localparam FMSB = WID==80 ? 63 :
                  WID==64 ? 51 :
				  WID==52 ? 39 :
				  WID==48 ? 35 :
				  WID==44 ? 31 :
				  WID==42 ? 29 :
				  WID==40 ? 28 :
				  WID==32 ? 22 :
				  WID==24 ? 15 : 9;

input [WID-1:0] a, b;
output [3:0] o;
reg [3:0] o;
output nanx;

// Decompose the operands
wire sa;
wire sb;
wire [EMSB:0] xa;
wire [EMSB:0] xb;
wire [FMSB:0] ma;
wire [FMSB:0] mb;
wire az, bz;
wire nan_a, nan_b;

fpDecompose #(WID) u1(.i(a), .sgn(sa), .exp(xa), .man(ma), .fract(), .xz(), .mz(), .vz(az), .inf(), .xinf(), .qnan(), .snan(), .nan(nan_a) );
fpDecompose #(WID) u2(.i(b), .sgn(sb), .exp(xb), .man(mb), .fract(), .xz(), .mz(), .vz(bz), .inf(), .xinf(), .qnan(), .snan(), .nan(nan_b) );

wire unordered = nan_a | nan_b;

wire eq = (az & bz) || (a==b);	// special test for zero
wire gt1 = {xa,ma} > {xb,mb};
wire lt1 = {xa,ma} < {xb,mb};

wire lt = sa ^ sb ? sa & !(az & bz): sa ? gt1 : lt1;

always @(unordered or eq or lt)
begin
	o[0] = eq;
	o[1] = lt;
	o[2] = lt1;
	o[3] = unordered;
end

// an unorder comparison will signal a nan exception
//assign nanx = op!=`FCOR && op!=`FCUN && unordered;
assign nanx = 1'b0;

endmodule

