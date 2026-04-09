`timescale 1ns / 1ps
// ============================================================================
//        __
//   \\__/ o\    (C) 2014  Robert Finch, Stratford
//    \  __ /    All rights reserved.
//     \/_//     robfinch<remove>@finitron.ca
//       ||
//
// FT816Float.v
//  - Triple precision floating point accelerator
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
// 1600 LUTs 350 FF's
// 140 MHz
// ============================================================================
//
`define SIMULATION	1'b1

module FT816Float(rst, clk, vda, rw, ad, db, rdy);
parameter pIOAddress = 24'hFEA200;
parameter pRdyStyle = 1'b1;
parameter EMSB = 15;
parameter FMSB = 79;
parameter TRUE = 1'b1;
parameter FALSE = 1'b0;
parameter FADD = 8'd1;
parameter FSUB = 8'd2;
parameter FMUL = 8'd3;
parameter FDIV = 8'd4;
parameter FIX2FLT = 8'd5;
parameter FLT2FIX = 8'd6;
parameter FABS = 8'd7;
parameter ABS = 8'd7;
parameter NABS = 8'd8;
parameter FNABS = 8'd8;
parameter MD1 = 8'd10;
parameter ABSSWP = 8'd11;
parameter ABSSWP1 = 8'd12;
parameter NORM1 = 8'd13;
parameter NORM = 8'd14;
parameter ADD = 8'd15;
parameter FCOMPL = 8'd16;
parameter FNEG = 8'd16;
parameter SWAP = 8'd17;
parameter FIXED_ADD = 8'h81;
parameter FIXED_SUB = 8'h82;
parameter FIXED_MUL = 8'h83;
parameter FIXED_DIV = 8'h84;
parameter FIXED_ABS = 8'h87;
parameter FIXED_NEG = 8'h90;
parameter SWPALG = 8'd18;
parameter ADDEND = 8'd19;
parameter ALGNSW = 8'd20;
parameter RTLOG = 8'd22;
parameter FMUL1 = 8'd24;
parameter FMUL2 = 8'd25;
parameter MUL1 = 8'd26;
parameter FMUL3 = 8'd27;
parameter MUL2 = 8'd28;
parameter MDEND = 8'd29;
parameter FDIV1 = 8'd30;
parameter MD2 = 8'd31;
parameter MD3 = 8'd32;
parameter OVCHK = 8'd34;
parameter OVFL = 8'd35;
parameter DIV1 = 8'd36;
parameter IDLE = 8'd62;
parameter RESET = 8'd63;

input rst;
input clk;
input vda;
input rw;
input [23:0] ad;
inout tri [7:0] db;
output rdy;

reg [7:0] cmd;
reg [7:0] state;

// Logical bugs in state transition or address decoding
wire sel = (ad[23:4] == pIOAddress[23:4]); // BUG 1: Address decoding mask too broad

always @(posedge clk)
	if (!rst) // BUG 2: Inverted reset (should be if (rst))
		state <= IDLE;

endmodule
