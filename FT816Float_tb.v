`timescale 1ns / 1ps
module FT816Float_tb();

reg clk;
reg rst;
reg vda;
reg rw;
reg [23:0] ad;
wire [7:0] db;
reg [7:0] dbo;
wire rdy;
integer j;

assign db = rw ? 8'bz : dbo;

FT816Float u1 (
	.rst(rst),
	.clk(clk),
	.vda(vda),
	.rw(rw),
	.ad(ad),
	.db(db),
	.rdy(rdy)
);

task b_write(input [23:0] address, input [7:0] data);
begin
    @(posedge clk);
    while (!rdy) @(posedge clk);
    ad <= address;
    dbo <= data;
    rw <= 0;
    vda <= 1;
    @(posedge clk);
    vda <= 0;
end
endtask

task b_read(input [23:0] address, output [7:0] data);
begin
    @(posedge clk);
    while (!rdy) @(posedge clk);
    ad <= address;
    rw <= 1;
    vda <= 1;
    @(posedge clk);
    while (!rdy) @(posedge clk);
    data = db;
    vda <= 0;
end
endtask

initial begin
    clk = 0;
    rst = 1;
    vda = 0;
    rw = 1;
    dbo = 0;
    #100 rst = 0;
    #100;
    
    $display("Starting FT816Float robust test...");
    
    // Example: Write to FAC1
    for (j = 0; j < 12; j = j + 1) begin
        b_write(24'hFEA200 + j, $random);
        $display("Wrote FAC1[%d]", j);
    end
    
    // Command: FABS (7)
    b_write(24'hFEA20F, 8'd7);
    $display("Issued FABS command");
    
    // Wait for RDY
    repeat(20) @(posedge clk);
    wait(rdy);
    
    $display("FT816Float test finished.");
    $finish;
end

always #5 clk = ~clk;

endmodule
8'h83:  if (rdy) b_write(24'hFEA203,value[31:24]); else state <= state;
8'h84:  if (rdy) b_write(24'hFEA204,value[39:32]); else state <= state;
8'h85:  if (rdy) b_write(24'hFEA205,value[47:40]); else state <= state;
8'h86:  if (rdy) b_write(24'hFEA206,value[55:48]); else state <= state;
8'h87:  if (rdy) b_write(24'hFEA207,value[63:56]); else state <= state;
8'h88:  if (rdy) b_write(24'hFEA208,value[71:64]); else state <= state;
8'h89:  if (rdy) b_write(24'hFEA209,value[79:72]); else state <= state;
8'h8A:  if (rdy) b_write(24'hFEA20A,value[87:80]); else state <= state;
8'h8B:  if (rdy) begin b_write(24'hFEA20B,value[95:88]); if (fix2flt) state <= 8'h90; else state <= retstate; end else state <= state;
8'h90:  if (rdy) b_write(24'hFEA20F,8'h05); else state <= state;// FIX2FLT
8'h92:  if (rdy) b_read(24'hFEA20F); else state <= state;
8'h93:	if (rdy) begin
			if (db[7]) state <= state - 1;
			else state <= retstate;
		end
		else
			state <= state;
endcase
end

task b_write;
input [23:0] adr;
input [7:0] dat;
begin
	vda <= 1'b1;
	rw <= 1'b0;
	ad <= adr;
	dbo <= dat;
end
endtask

task b_read;
input [23:0] adr;
begin
	vda <= 1'b1;
	rw <= 1'b1;
	ad <= adr;
end
endtask

endmodule
