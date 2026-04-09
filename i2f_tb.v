module i2f_tb;
    parameter FPWID = 32;
    `include "fpSize.sv"
    
    reg clk;
    reg ce;
    reg [2:0] rm;
    reg [FPWID-1:0] i;
    wire [FPWID-1:0] o;
    integer j;

    i2f #(FPWID) uut (.clk(clk), .ce(ce), .rm(rm), .i(i), .o(o));

    initial begin
        clk = 0;
        ce = 1;
        rm = 3'b000;
        i = 0;
        $display("Running robust simulation for i2f...");
        
        // Fixed cases
        i = 32'd1; #20;
        $display("i=%d (1) | o=%h", i, o);

        i = 32'd100; #20;
        $display("i=%d (100) | o=%h", i, o);

        for (j = 0; j < 20; j = j + 1) begin
            i = $random;
            #20;
            $display("i=%d | o=%h", i, o);
        end
        
        $display("Simulation for i2f finished.");
        $finish;
    end

    always #5 clk = ~clk;
endmodule
