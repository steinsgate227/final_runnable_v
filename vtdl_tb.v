module vtdl_tb;
    parameter WID = 8;
    reg clk;
    reg ce;
    reg [3:0] a;
    reg [WID-1:0] d;
    wire [WID-1:0] q;
    integer j;

    vtdl #(WID) uut (.clk(clk), .ce(ce), .a(a), .d(d), .q(q));

    initial begin
        clk = 0;
        ce = 1;
        a = 0;
        d = 0;
        $display("Running robust simulation for vtdl...");
        
        #20;
        for (j = 0; j < 32; j = j + 1) begin
            @(posedge clk);
            d <= j[7:0];
            a <= j % 16;
            #1;
            $display("Time=%t | d=%h | a=%d | q=%h", $time, d, a, q);
        end
        
        $display("Simulation for vtdl finished.");
        $finish;
    end

    always #5 clk = ~clk;
endmodule
