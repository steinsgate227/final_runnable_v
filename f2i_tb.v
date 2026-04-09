module f2i_tb;
    parameter FPWID = 32;
    `include "fpSize.sv"
    
    reg clk;
    reg ce;
    reg [MSB:0] i;
    wire [MSB:0] o;
    wire overflow;
    integer j;

    f2i #(FPWID) uut (.clk(clk), .ce(ce), .i(i), .o(o), .overflow(overflow));

    initial begin
        clk = 0;
        ce = 1;
        i = 0;
        $display("Running robust simulation for f2i...");
        
        // Some fixed test cases
        i = 32'h40000000; // 2.0
        #20;
        $display("i=%h (2.0) | o=%h | overflow=%b", i, o, overflow);
        
        i = 32'h42C80000; // 100.0
        #20;
        $display("i=%h (100.0) | o=%h | overflow=%b", i, o, overflow);

        for (j = 0; j < 20; j = j + 1) begin
            i = $random;
            #20;
            $display("i=%h | o=%h | overflow=%b", i, o, overflow);
        end
        
        $display("Simulation for f2i finished.");
        $finish;
    end

    always #5 clk = ~clk;
endmodule
