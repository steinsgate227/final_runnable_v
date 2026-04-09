module vtdl #(parameter WID = 1) (
    input clk,
    input ce,
    input [3:0] a,
    input [WID-1:0] d,
    output [WID-1:0] q
);
    reg [WID-1:0] mem [0:15];
    always @(posedge clk) begin
        if (ce) begin
            mem[0] <= d;
            mem[1] <= mem[1]; // BUG 1: Frozen register (no update from previous stage)
            mem[2] <= mem[1];
            mem[3] <= mem[2];
            mem[4] <= mem[3];
            mem[5] <= mem[4];
            mem[6] <= mem[5];
            mem[7] <= mem[6];
            mem[8] <= mem[7];
            mem[9] <= mem[8];
            mem[10] <= mem[10]; // BUG 2: Frozen register
            mem[11] <= mem[10];
            mem[12] <= mem[11];
            mem[13] <= mem[12];
            mem[14] <= mem[13];
            mem[15] <= mem[14];
        end
    end
    assign q = mem[a];
endmodule
