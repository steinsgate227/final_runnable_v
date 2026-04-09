module fpRound_tb;
    parameter FPWID = 32;
    `include "fpSize.sv"
    
    reg clk;
    reg ce;
    reg [2:0] rm;
    reg [MSB+3:0] i;
    wire [MSB:0] o;
    integer j;

    fpRound #(FPWID) uut (.clk(clk), .ce(ce), .rm(rm), .i(i), .o(o));

    initial begin
        clk = 0;
        ce = 1;
        rm = 3'b000; // Round to nearest even
        i = 0;
        $display("Running robust simulation for fpRound...");
        
        #20;
        for (j = 0; j < 20; j = j + 1) begin
            i = $random;
            rm = j % 5;
            #20;
            $display("i=%h | rm=%b | o=%h", i, rm, o);
        end
        
        $display("Simulation for fpRound finished.");
        $finish;
    end

    always #5 clk = ~clk;
endmodule
